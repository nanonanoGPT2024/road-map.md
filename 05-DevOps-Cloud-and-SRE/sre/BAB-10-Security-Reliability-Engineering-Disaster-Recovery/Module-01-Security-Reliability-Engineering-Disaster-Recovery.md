# Module 01: Security Reliability Engineering (SRE-Sec) & Disaster Recovery

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menghitung dan menetapkan metrik bisnis kritis: **Recovery Time Objective (RTO)** dan **Recovery Point Objective (RPO)** dengan pemetaan toleransi data loss.
- Merancang, menganalisis komparasi biaya, dan mengimplementasikan empat pola Disaster Recovery (DR): **Backup & Restore**, **Pilot Light**, **Warm Standby**, dan **Multi-Region Active-Active**.
- Membangun pipeline otomatisasi validasi integritas backup dan replikasi data asinkron/sinkron melintasi region geografis.
- Mengaplikasikan prinsip **Security Chaos Engineering (SCE)** untuk menguji ketahanan kontrol keamanan dan mekanisme deteksi ancaman saat degradasi sistem.
- Menyusun, menguji, dan mengeksekusi **DR Game Day Runbook** berstandar enterprise yang mencakup orkestrasi DNS failover, split-brain mitigation, dan data reconciliation.

---

## 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam tentang:
- Arsitektur jaringan cloud: VPC peering, Transit Gateway, Anycast DNS, BGP routing, dan Global Server Load Balancing (GSLB).
- Dasar-dasar replikasi sistem basis data relasional (PostgreSQL/MySQL write-ahead logging (WAL), binlog replication, synchronous vs. asynchronous quorum).
- Praktik Infrastructure as Code (Terraform) dan orkestrasi kontainer (Kubernetes).
- Prinsip dasar SRE: Service Level Indicators (SLI), Service Level Objectives (SLO), dan Incident Command System (ICS).

---

## 3. Concept
Disaster Recovery (DR) dan Security Reliability Engineering (SRE-Sec) adalah disiplin konvergen yang memperlakukan skenario bencana—baik degradasi infrastruktur fisik, padamnya penyedia cloud (cloud outage), serangan ransomware, maupun kebocoran kredensial massal—sebagai kegagalan deterministik yang harus dimitigasi melalui desain sistem perangkat lunak, otomatisasi, dan verifikasi berkelanjutan. 

Alih-alih memandang DR sebagai sekadar polis asuransi pasif yang diuji setahun sekali secara manual, SRE-Sec memandang kesiapan pemulihan sebagai properti operasional dinamis dari sistem produksi yang diuji secara empiris menggunakan injeksi anomali, otomatisasi failover kontinu, dan pembuktian matematis integritas data (RPO zero verification).

---

## 4. Why
Ketiadaan strategi DR dan SRE-Sec yang teruji secara matematis dan operasional mengakibatkan:
1. **Financial Catastrophe**: Downtime pada sistem pembayaran atau core banking menghasilkan denda regulasi (seperti OJK, BI, GDPR), kehilangan transaksi langsung, serta penalti SLA jutaan dolar per jam.
2. **Permanent Data Loss**: Mengandalkan mekanisme snapshot penyimpanan tanpa validasi transaksional sering kali menghasilkan data korup (*silent data corruption* atau *torn pages*) saat pemulihan, yang melanggar batas toleransi RPO.
3. **Ransomware Vulnerability**: Backup lokal yang tidak memiliki isolasi kriptografis (*air-gapped* / *immutable storage*) rentan terenkripsi atau terhapus bersamaan dengan infrastruktur utama selama serangan siber terkoordinasi.
4. **Human Execution Paralysis**: Dokumentasi runbook yang usang membuat insinyur melakukan kesalahan manusia (*human error*) fatal seperti memicu split-brain saat mengeksekusi failover di bawah tekanan insiden riil.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 RTO dan RPO: Batasan Fisika dan Finansial
- **RPO (Recovery Point Objective)**: Jumlah maksimum kehilangan data yang dapat ditoleransi oleh bisnis, diukur dalam satuan waktu ke belakang dari titik insiden.
  - $RPO = 0$: Membutuhkan replikasi tersinkronisasi (*synchronous replication*), two-phase commits (2PC), atau konsensus Raft/Paxos lintas region. Batasan latensi jaringan cahaya dalam serat optik ($\approx 5\text{ ms per } 1000\text{ km}$) membatasi throughput tulis.
  - $RPO > 0$: Memanfaatkan replikasi asinkron (*asynchronous replication*). Terdapat *replication lag* yang berpotensi menghilangkan transaksi yang masih berada di buffer antrean (*in-flight data*) saat region primer tumbang.
- **RTO (Recovery Time Objective)**: Durasi waktu maksimum yang diperbolehkan untuk memulihkan sistem kembali beroperasi penuh setelah bencana dideklarasikan.
  - $RTO \approx 0$: Memerlukan routing dinamis otomatis (Anycast DNS / Cloudflare Magic Transit / AWS Route53 Application Recovery Controller) dengan health-check mendalam dan arsitektur Active-Active.

### 5.2 Anatomi 4 Pola Disaster Recovery

| Pola DR | Karakteristik Arsitektur | Target RTO | Target RPO | Biaya Relatif | Kompleksitas Teknis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Backup & Restore** | Data di-snapshot, dikirim ke object storage region sekunder, dan di-enkripsi immutably. Infrastruktur compute dibuat ulang on-demand via IaC saat bencana. | Jam s.d. Hari | Jam s.d. 24 Jam | $\$$ | Rendah |
| **Pilot Light** | Data direplikasi kontinu ke region sekunder (misal DB Read Replica aktif). Core compute (Kubernetes control plane, routing) nonaktif atau bernilai minimum (1 node). | 10 - 30 Menit | Detik s.d. Menit | $\$ \$$ | Menengah |
| **Warm Standby** | Infrastruktur sekunder berjalan penuh namun diperkecil skalanya (*scaled down*, misal 20% kapasitas compute). Siap melayani beban parsial dan auto-scale seketika. | Menit (< 5 Menit) | Detik | $\$ \$ \$$ | Tinggi |
| **Multi-Region Active-Active** | Beban trafik dibagi kontinu antar region (50-50 atau geolokasi terdekat). Basis data multi-region terdistribusi sinkron/asinkron dengan mekanisme resolusi konflik. | $\approx 0$ (Sub-detik/Detik)| Mendekati 0 | $\$ \$ \$ \$$ | Sangat Tinggi |

### 5.3 Automated Data Replication & Backup Validation
- **Cryptographic Immutability**: Menggunakan fitur Object Lock (WORM - Write Once Read Many) berbasis kepatuhan hukum (*compliance mode*) yang mencegah penghapusan backup bahkan oleh root/admin account selama masa retensi.
- **Continuous Backup Verification Pipeline**: Menjadwalkan pengujian non-destruktif harian di mana sistem secara otomatis:
  1. Melakukan restore snapshot ke ephemeral database instance terisolasi di region target.
  2. Menjalankan skrip validasi integritas relasional (foreign key consistency check, checksum verification).
  3. Menguji *synthetic queries* terhadap data terbaru untuk memastikan konsistensi transaksional.
  4. Menghancurkan (*teardown*) instance pengujian dan memancarkan metrik validasi ke dashboard observabilitas.

### 5.4 Security Chaos Engineering (SCE)
SCE menerapkan prinsip Chaos Engineering ke domain keamanan dan ketahanan siber:
- **Failure Injection Types**:
  - *Certificate Revocation*: Menghapus CA cert secara tiba-tiba untuk memverifikasi apakah layanan fallback secara aman atau mengalami *hard crash*.
  - *Firewall / IAM Drift*: Secara sengaja mencabut permission role KMS atau memotong port VPC peering database untuk menguji apakah sistem alerting SRE-Sec mendeteksi anomali dalam toleransi SLO (< 60 detik).
  - *Ransomware Simulation*: Memblokir akses ke disk volume stateful dan menguji apakah sistem secara otomatis mendegradasi layanan ke *safe read-only mode* tanpa kebocoran memori.

### 5.5 Disaster Recovery Game Day Runbooks
Game Day Runbook modern harus bersifat *executable* dan *declarative*. Bukan sekadar PDF statis, melainkan arsitektur langkah operasional yang menetapkan:
- **Blast Radius Boundaries**: Mekanisme isolasi kegagalan agar pengujian tidak meluas ke sistem produksi utama.
- **Definitive Decision Matrix**: Ambang batas terukur kapan SRE Commander harus menyatakan DR Failover (misal: "Database primer unreachable selama 300 detik BERTURUT-TURUT DAN replication lag region B bernilai < 10 detik").
- **Split-Brain Mitigation**: Mekanisme *STONITH* (*Shoot The Other Node In The Head*) atau degradasi kuorum untuk mematikan hak tulis region primer secara permanen sebelum mempromosikan region sekunder menjadi master.
- **Rollback / Failback Protocol**: Langkah rekonsiliasi data *delta* yang tertinggal pasca region primer hidup kembali sebelum trafik dialihkan kembali.

---

## 6. How
Implementasi framework DR & SRE-Sec dijalankan melalui langkah operasional berikut:
1. **Audit & Klasifikasi Aset**: Kelompokkan dependensi sistem berdasarkan Tier (Tier-1: Pembayaran/Auth - Target RTO < 5m, RPO 0; Tier-2: Katalog/Reporting - Target RTO < 4h, RPO < 1h).
2. **Konfigurasi Replikasi Storage & Database**: Terapkan enkripsi KMS lintas region (Cross-Region CMK) dan replikasi kontinu berbasis WAL atau binlog streaming.
3. **Penyusunan IaC Idempoten**: Gunakan Terraform untuk mendeklarasikan infrastruktur region pemulihan secara identik (network, security group, IAM policies).
4. **Otomatisasi Validasi Restorasi**: Buat pipeline CI/CD (GitHub Actions / Argo Workflows) yang menjadwalkan restorasi otomatis harian dan verifikasi data checksum.
5. **Implementasi Routing Failover DNS / Anycast**: Konfigurasi health check dengan skema inversi kuorum (*quorum-based inversion*) untuk mencegah flapping DNS.
6. **Eksekusi Game Day Terjadwal**: Jalankan simulasi bencana berkala dengan menginjeksi skenario kegagalan tanpa memberi tahu operator secara detail, guna menguji kesiapan manusia dan sistem.

---

## 7. Analogy
Bayangkan sebuah bank sentral dengan brankas uang fisik:
- **Backup & Restore**: Tiap malam bank memotret isi brankas dan mencatat nomor seri uang di kertas, lalu membawanya ke kota lain. Jika bank terbakar, mereka harus menyewa gedung baru, membeli brankas baru, lalu meminta percetakan uang mencetak kembali uang berdasarkan catatan tersebut (Memerlukan waktu berhari-hari).
- **Pilot Light**: Bank memiliki bangunan cadangan kecil di kota lain dengan brankas kecil yang selalu menerima salinan buku kas harian secara instan. Staf teller belum ada. Jika kantor utama meledak, mereka menyalakan listrik penuh dan memanggil semua staf cadangan untuk mulai bekerja (RTO 30 menit).
- **Warm Standby**: Gedung cadangan sudah menyala, beroperasi melayani segelintir nasabah lokal (kapasitas 20%). Jika bank utama hancur, gedung cadangan langsung membuka seluruh pintu loket dan memanggil staf tambahan (RTO hitungan menit).
- **Active-Active**: Bank memiliki dua gedung identik di dua kota yang beroperasi 100% bersamaan. Nasabah bebas masuk ke gedung mana pun; tiap uang yang disetor di gedung A langsung tercatat di sistem komputer gedung B secara real-time. Jika gedung A hancur akibat gempa, semua nasabah langsung diarahkan ke gedung B tanpa jeda transaksi.

---

## 8. Diagram (ASCII)

```
                 =======================================================
                                TRAFFIC MANAGEMENT & GSLB
                 =======================================================
                                            │
                                  [ Route 53 / Anycast ]
                                 (Health Checks / Routing)
                                  ┌─────────┴─────────┐
                     Route 100%   │                   │  Failover 
                     Normal Ops   ▼                   ▼  (Disaster)
         ==================================   ==================================
         REGION PRIMARY (ap-southeast-1)      REGION SECONDARY (ap-southeast-3)
         ==================================   ==================================
         ┌────────────────────────────────┐   ┌────────────────────────────────┐
         │ VPC Ingress / Load Balancer    │   │ VPC Ingress / Load Balancer    │
         └──────────────┬─────────────────┘   └──────────────┬─────────────────┘
                        │                                    │
         ┌──────────────▼─────────────────┐   ┌──────────────▼─────────────────┐
         │ Compute Clusters (K8s)         │   │ Standby/Scaled Compute Cluster │
         │ (Active Workloads: 100%)       │   │ (Pilot: 0% / Warm: 25-100%)    │
         └──────────────┬─────────────────┘   └──────────────┬─────────────────┘
                        │                                    │
                        ▼                                    ▼
         ┌────────────────────────────────┐   ┌────────────────────────────────┐
         │ Database Master (Read/Write)   │   │ Database Replica (Read-Only)   │
         │ (Aurora/PostgreSQL Primary)    │   │ (Standby Replica)              │
         └───────┬────────────────────────┘   └───────▲────────────────────────┘
                 │                                    │
                 │   Async Replication (Streaming WAL)│
                 ├────────────────────────────────────┘
                 │
                 │ Immutable Encrypted Snapshots (KMS)
                 ▼
         ┌────────────────────────────────┐   Cross-Region   ┌────────────────────────────────┐
         │ AWS S3 Bucket (Primary)        │── Replication ──>│ AWS S3 Bucket (Disaster Rec)  │
         │ - Object Lock (Compliance WORM)│                  │ - Object Lock (WORM Enforced)  │
         └────────────────────────────────┘                  └────────────────────────────────┘
                                                                             │
                                                             Daily Automated │ Restore Test
                                                                             ▼
                                                             ┌────────────────────────────────┐
                                                             │ Ephemeral Validation Engine    │
                                                             │ (Restore -> Test -> Teardown)  │
                                                             └────────────────────────────────┘
```

---

## 9. Simple Example
Skrip shell sederhana untuk memeriksa keterlambatan replikasi PostgreSQL (*replication lag*) sebelum memutus apakah aman memicu failover otomatis (RPO protection check):

```bash
#!/usr/bin/env bash
set -euo pipefail

# Konfigurasi ambang batas toleransi RPO dalam byte (misal: 10MB)
MAX_ALLOWED_LAG_BYTES=10485760 

# Dapatkan replication lag dari replica instance
LAG_BYTES=$(psql -h dr-replica.internal.corp -U postgres -t -A -c \
  "SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), pg_last_wal_receive_lsn());")

echo "Current Replication Lag: ${LAG_BYTES} bytes"

if [ "${LAG_BYTES}" -gt "${MAX_ALLOWED_LAG_BYTES}" ]; then
  echo "CRITICAL: Replication lag melampaui ambang batas RPO!"
  echo "Abort failover otomatis untuk mencegah data loss masif. Butuh intervensi manual SRE Commander."
  exit 1
else
  echo "OK: Replication lag dalam batas toleransi. Layak dipromosikan sebagai Master baru."
  # psql -h dr-replica.internal.corp -U postgres -c "SELECT pg_promote();"
fi
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Kode Hands-on)

Berikut adalah definisi Terraform untuk mengonfigurasi S3 Immutable Storage dengan Cross-Region Replication (CRR) dan Object Lock berbasis Compliance Mode guna menangkal ancaman ransomware dan memastikan perlindungan RPO.

```hcl
# Provider Region Primer
provider "aws" {
  alias  = "primary"
  region = "ap-southeast-1"
}

# Provider Region Sekunder (Disaster Recovery)
provider "aws" {
  alias  = "secondary"
  region = "ap-southeast-3"
}

# KMS Key di DR Region untuk Dekripsi/Enkripsi Snapshot
resource "aws_kms_key" "dr_backup_key" {
  provider                = aws.secondary
  description             = "KMS Key for DR Immutable Backups"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

# Bucket S3 Sekunder (DR Target) dengan Object Lock Aktif
resource "aws_s3_bucket" "dr_backup_bucket" {
  provider      = aws.secondary
  bucket        = "corp-critical-data-dr-storage"
  force_destroy = false

  object_lock_configuration {
    object_lock_enabled = "Enabled"
  }
}

# Mengaktifkan Compliance Mode Retention (WORM: Kebijakan tidak bisa dicabut oleh siapapun)
resource "aws_s3_bucket_object_lock_configuration" "dr_lock" {
  provider = aws.secondary
  bucket   = aws.s3_bucket.dr_backup_bucket.id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = 90
    }
  }
}

# Bucket S3 Primer (Data Source)
resource "aws_s3_bucket" "primary_bucket" {
  provider = aws.primary
  bucket   = aws.primary_bucket_name

  versioning {
    enabled = true
  }
}

# IAM Role untuk S3 Cross-Region Replication
resource "aws_iam_role" "replication" {
  provider = aws.primary
  name     = "s3-cross-region-replication-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "s3.amazonaws.com"
      }
    }]
  })
}

# Konfigurasi Replikasi Asinkron Otomatis Lintas Region
resource "aws_s3_bucket_replication_configuration" "replication_config" {
  provider = aws.primary
  role     = aws_iam_role.replication.arn
  bucket   = aws_s3_bucket.primary_bucket.id

  rule {
    id     = "ContinuousReplicationToDR"
    status = "Enabled"

    destination {
      bucket        = aws_s3_bucket.dr_backup_bucket.arn
      storage_class = "STANDARD_IA"

      encryption_configuration {
        replica_kms_key_id = aws_kms_key.dr_backup_key.arn
      }
    }

    source_selection_criteria {
      sse_kms_encrypted_objects {
        status = "Enabled"
      }
    }
  }
}
```

---

## 11. Real World Example
Pada kasus industri nyata perbankan digital:
Sebuah bank digital mengalami insiden di mana region cloud utama (*ap-southeast-1*) mengalami degradasi jaringan total akibat kerusakan physical backbone fiber bawah laut yang memicu packet loss sebesar 70% dan lonjakan error rate ke 85%. 

**Tindakan SRE-Sec**:
1. Metrik Synthetic Health Check berbasis gRPC mendeteksi ambang batas kegagalan di 3 edge point berbeda selama 180 detik.
2. Insinyur SRE memverifikasi metrik *Replication Lag* database sekunder di Jakarta (*ap-southeast-3*) yang tercatat stabil di angka 1.2 detik (dalam batas aman RPO bisnis < 5 detik).
3. Melalui Game Day Runbook terotomatisasi, SRE Commander memicu *Automated Fencing Script* yang mengeksekusi degradasi kuorum: IAM credentials cluster region Singapura dicabut secara otomatis melalui API control plane global untuk mencegah *split-brain write operations*.
4. Database sekunder di Jakarta dipromosikan menjadi Master.
5. Record routing Route 53 Application Recovery Controller dialihkan secara instan menuju ingress controller Jakarta.
6. **Hasil Akhir**: Total RTO pemulihan tercatat 4 menit 12 detik, RPO tercatat 1.2 detik kehilangan transaksi minor yang langsung direkonsiliasi otomatis via Kafka dead-letter re-drive. Layanan kembali beroperasi normal tanpa intervensi manual di level konfigurasi OS.

---

## 12. Trade-offs

```
              BIAYA / KOMPLEKSITAS
                     ▲
                     │                                  [Active-Active]
                     │                                 (RTO≈0, RPO≈0)
                     │
                     │                       [Warm Standby]
                     │                      (RTO: Mins, RPO: Secs)
                     │
                     │            [Pilot Light]
                     │           (RTO: <30m, RPO: Mins)
                     │
                     │   [Backup & Restore]
                     │  (RTO: Hours, RPO: Hours)
                     └─────────────────────────────────────────────► PERFORMA PEMULIHAN
                                                                     (RTO & RPO Terendah)
```

- **Active-Active vs. Biaya Infrastruktur**: Memberikan RTO/RPO mendekati 0, namun biaya operasional meningkat > 100% karena sistem menduplikasi compute dan network transfer lintas region secara terus-menerus. Selain itu, kompleksitas aplikasi melonjak karena harus menangani *conflict resolution* (CRDTs atau distributed locking).
- **Synchronous vs. Asynchronous Replication**: Replikasi sinkron menjamin RPO = 0, tetapi menambahkan latensi *round-trip time* (RTT) jaringan pada setiap operasi penulisan basis data (penurunan drastis pada write throughput aplikasi). Replikasi asinkron mempertahankan performa latensi aplikasi primer, namun mengorbankan sebagian data saat bencana tak terduga terjadi.
- **Strict Compliance Locks vs. Agilitas Operasional**: S3 Object Lock Compliance Mode menjamin perlindungan mutlak dari ransomware, namun jika terjadi kesalahan konfigurasi deployment yang membanjiri bucket dengan jutaan objek sampah, objek tersebut TIDAK DAPAT dihapus oleh siapa pun hingga durasi retensi habis, menimbulkan lonjakan biaya penyimpanan yang tidak bisa dihindari.

---

## 13. When To Use
- Terapkan **Multi-Region Active-Active** hanya untuk sistem mission-critical Tier-0 (misal: settlement perbankan, sistem otentikasi global, atau payment gateway) di mana downtime bernilai ratusan ribu dolar per menit.
- Terapkan **Warm Standby** untuk sistem core e-commerce, telekomunikasi, atau SaaS enterprise tingkat tinggi.
- Terapkan **Pilot Light** untuk aplikasi operasional internal atau sistem dengan SLA toleransi downtime 15-30 menit.
- Terapkan **Automated Backup Validation** pada SEMUA sistem yang menyimpan data persisten tanpa terkecuali.

---

## 14. When NOT To Use
- Jangan gunakan **Multi-Region Active-Active** jika basis data Anda masih monolitik dan berbasis penguncian tabel relasional tradisional (misal: MySQL default engine tanpa distributed middleware) karena keterbatasan latensi jaringan lintas region akan memicu deadlock dan connection pool exhaustion.
- Jangan gunakan pola DR berbiaya tinggi (Warm Standby / Active-Active) untuk environment non-produksi (Dev/Staging/UAT); gunakan pendekatan *Infrastructure as Code on-demand recreation* untuk menghemat biaya.
- Jangan mengaktifkan *fully automated zero-human-in-the-loop failover* jika mekanisme deteksi kesehatan (*health check*) Anda belum memiliki sistem anti-flapping (hysteresis) yang matang, karena dapat memicu osilasi failover berulang (*ping-pong failure*).

---

## 15. Common Mistakes
- **The "Untested Backup" Fallacy**: Menganggap sistem memiliki DR hanya karena script `pg_dump` atau snapshot disk berjalan tiap malam, tanpa pernah melakukan simulasi restore secara terprogram. Snapshot yang korup baru diketahui saat bencana riil terjadi.
- **Split-Brain Disaster**: Mempromosikan node database sekunder menjadi master baru sementara node primer lama ternyata masih menerima trafik tulis parsial. Hal ini menyebabkan inkonsistensi data yang bercabang dan memerlukan rekonsiliasi manual yang sangat menyakitkan.
- **Ignoring IAM & KMS Dependencies**: Memindahkan beban komputasi ke region baru namun lupa mereplikasi kunci KMS pengenkripsi atau role IAM yang dibutuhkan. Instance baru gagal *booting* karena gagal mendekripsi *secrets* atau volume storage.
- **Hardcoded Endpoints**: Menyematkan DNS atau IP region primer secara hardcoded di layer aplikasi mikro, membuat failover DNS global menjadi sia-sia karena aplikasi internal tetap mengakses region yang tumbang.

---

## 16. Best Practices
1. **Immutable Infrastructure Declarations**: Seluruh topologi DR wajib dideklarasikan via Terraform atau GitOps (ArgoCD) yang secara periodik disinkronisasikan secara otomatis agar tidak terjadi *configuration drift* antar region.
2. **Deterministic STONITH Strategy**: Pastikan ada skrip isolasi otomatis yang mencabut hak akses jaringan (*security group revocation*) atau mematikan instance primer sebelum instance sekunder dipromosikan.
3. **Automated Recovery Testing**: Buat workflow otomatis mingguan yang merestorasi data backup ke instance sementara, menjalankan query sanitasi, lalu menghancurkan resource tersebut.
4. **Regular Chaos Game Days**: Selenggarakan latihan tanggap darurat kuartalan dengan skenario acak: mensimulasikan pemadaman region, insiden ransomware, atau kehilangan sertifikat TLS.

---

## 17. Troubleshooting

| Masalah / Gejala | Akar Masalah Potensial | Tindakan Remediasi / Solusi |
| :--- | :--- | :--- |
| Database sekunder menolak dipromosikan menjadi Master. | Replikasi WAL macet atau terdapat *unapplied transactions* di buffer standby. | Periksa `pg_stat_recovery_prefetch`. Jalankan `pg_wal_replay_resume()` jika proses replay dalam keadaan *paused*. Paksa promosi via CLI hanya jika batas RPO disetujui untuk dikorbankan. |
| Split-Brain: Kedua database di Region A dan B menerima operasi Write. | GSLB / DNS memicu failover tanpa mengisolasi node primer lama (*failed fencing*). | Segera set database Region A ke mode `READ_ONLY` atau isolasi security group-nya. Ekstrak data transaksi unik di Region A menggunakan LSN/timestamp, lalu lakukan rekonsiliasi ke Region B. |
| Restore snapshot gagal dengan error: `Access Denied to KMS Key`. | Region sekunder tidak memiliki otorisasi ke KMS Key atau CMK belum di-share lintas region. | Periksa KMS Key Policy di Region DR. Pastikan IAM Role DR Instance memiliki action `kms:Decrypt` pada ARN Key yang sesuai. |
| Flapping DNS Failover (Trafik berpindah bolak-balik terus menerus). | Health check endpoint terlalu sensitif atau interval threshold terlalu pendek. | Terapkan *Health Check Hysteresis*: Naikkan kegagalan berturut-turut menjadi 5x sebelum failover, dan butuh 10x sukses berturut-turut sebelum failback. |

---

## 18. Exercise
1. Hitung total biaya data transfer lintas region untuk basis data relasional berukuran 5 TB dengan tingkat churn data penulisan harian sebesar 20% jika menggunakan replikasi kontinu.
2. Identifikasi potensi kelemahan arsitektur pada alur failover berikut:
   *Monitoring mengecek port HTTP 80 -> Health check gagal -> Cloudflare mengubah target DNS ke Region B -> Database Region B otomatis menerima koneksi.* (Petunjuk: Apa yang terjadi jika HTTP service mati tetapi database Region A masih aktif dan memproses antrean?)
3. Tuliskan sebuah policy IAM AWS berbasis JSON yang hanya memperbolehkan penghapusan bucket snapshot jika request menyertakan token MFA (Multi-Factor Authentication).

---

## 19. Challenge
Rancang arsitektur Disaster Recovery berstandar industri perbankan yang mencakup skenario:
- Region Primer: AWS Singapura (`ap-southeast-1`).
- Region Sekunder: AWS Jakarta (`ap-southeast-3`).
- Kebutuhan: RPO $\le$ 5 detik, RTO $\le$ 2 menit.
- Tantangan Khusus: Basis data PostgreSQL harus terlindung dari serangan *ransomware* internal (insider threat) yang memiliki akses Administrator. 

Gambarkan alur fungsional pemulihan kegagalan, strategi isolasi kriptografis, struktur *automated fencing*, serta mekanisme validasi integritas data pasca-pemulihan secara komprehensif dalam sebuah dokumen arsitektur teknis.

---

## 20. Summary
- **RTO dan RPO** adalah jangkar matematis penentu seluruh pilihan arsitektur DR; mengecilkan keduanya menuju nol meningkatkan biaya dan kompleksitas rekayasa perangkat lunak secara eksponensial.
- **Empat Pola DR Utama** (Backup & Restore, Pilot Light, Warm Standby, Active-Active) menawarkan trade-off nyata antara biaya pemeliharaan infrastruktur versus kecepatan restorasi layanan.
- **Security Reliability Engineering (SRE-Sec)** mengubah paradigma reaktif menjadi proaktif: pertahanan sistem terhadap bencana dan serangan siber harus dibuktikan secara empiris melalui otomatisasi validasi backup berkelanjutan dan injeksi kegagalan (*Chaos Engineering*).
- Kunci keberhasilan penanganan insiden bencana skala besar bertumpu pada **Game Day Runbooks** yang terotomatisasi secara deklaratif, disertai mekanisme *fencing* mutlak untuk mencegah petaka *split-brain*.

---