# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 10: Enterprise Security, Resiliency, & Disaster Recovery**  
**Kategori: 04-Backend-and-Database / Elasticsearch**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang & Mengonfigurasi Cross-Cluster Replication (CCR):** Mengimplementasikan topologi replikasi asinkron multi-cluster (Active-Passive dan Active-Active read) dengan kontrol *retention leases* dan *sequence numbers*.
2. **Membangun Arsitektur Disaster Recovery (DR) Multi-Region:** Menghitung dan mencapai target RPO (*Recovery Point Objective*) < 5 detik dan RTO (*Recovery Time Objective*) < 1 menit menggunakan CCR, GSLB, dan failover otomatis.
3. **Mengoptimalkan Storage Tiering Berbasis Searchable Snapshots:** Mengintegrasikan Snapshot Lifecycle Management (SLM) dengan storage object (AWS S3 / MinIO) untuk Cold dan Frozen tier guna memangkas biaya infrastruktur hingga 60% tanpa memutus akses pencarian.
4. **Menerapkan Zero-Trust Security End-to-End:** Mengonfigurasi mTLS (node-to-node dan client-to-node) menggunakan custom PKI, Document-Level Security (DLS), Field-Level Security (FLS), serta integrasi OpenID Connect (OIDC) / Active Directory.
5. **Memitigasi Split-Brain & Quorum Loss:** Mengonfigurasi *voting-only master nodes*, *shard allocation awareness*, dan *zone anti-affinity* pada deployment multi-AZ/multi-region.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
* Fundamental Elasticsearch: Sharding, Routing, Inverted Index, Segments, dan Translog.
* Pemahaman operasional TLS/x509: CA (*Certificate Authority*), SAN (*Subject Alternative Name*), Cipher Suites, dan format PEM/JKS.
* Konsep dasar jaringan enterprise: CIDR, Latensi WAN vs LAN, DNS Failover, Anycast BGP, MTU, dan NAT.
* Pengalaman mengoperasikan Linux system internals: `sysctl`, memory locking (`mlockall`), file descriptors, dan ephemeral storage volume.
* Telah menyelesaikan Bab 10 Modul 01 (Fundamental Security, RBAC dasar, dan backup manual via `_snapshot`).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Mekanisme Internal Cross-Cluster Replication (CCR)

CCR bekerja pada level Lucene engine dengan memanfaatkan **Retention Leases** dan **Sequence Numbers (`_seq_no`)**. Berbeda dengan replikasi internal intra-cluster yang bersifat *push* synchronous dari Primary ke Replica, CCR menerapkan pola **Pull-based Asynchronous Engine**.

```
[ Leader Cluster (Primary Shard) ]
       │
       ├─ Translog / Lucene Segment
       ├─ Soft Deletes Pool (index.soft_deletes.enabled: true)
       └─ Retention Lease Tracker (Menahan segment purge sampai Follower selesai membaca)
               ▲
               │ 1. Poll batch operasi via transport protocol (_seq_no > last_synced)
               │    (cluster.remote.<remote_cluster>.seeds)
               │
[ Follower Cluster (Follower Shard) ]
       │
       ├─ CCR Shard Follower Task (Background Persistent Task)
       ├─ Write buffer queue
       └─ Commit ke Engine lokal & update Global Checkpoint
```

1. **Soft Deletes:** Ketika dokumen di-update atau di-delete pada Leader Index, Lucene tidak langsung menghapus data fisik dari segment. Dokumen ditandai sebagai *soft deleted* dan dipertahankan berdasarkan `index.soft_deletes.retention_lease.period` (default: 12 jam).
2. **Follower Task:** Cluster follower menjalankan thread background yang secara berkala melakukan polling ke leader shard menggunakan RPC internal (Port 9300).
3. **Retention Leases:** Follower mendaftarkan *lease* ke shard leader. Leader tidak akan menjalankan *merge* untuk membuang soft-deletes sebelum sequence number follower melampaui retention lease tersebut. Jika follower tertinggal melewati batas waktu lease, replikasi rusak dan follower harus diinisialisasi ulang dari snapshot awal.

### 3.2 Searchable Snapshots & Tiering Storage (Cold & Frozen Tiers)

Searchable Snapshots mengubah paradigma penyimpanan indeks lama. Shard tidak perlu lagi di-mount secara penuh ke disk SSD NVMe lokal:

* **Cold Tier:** Shard bertindak sebagai cache lokal parsial. Snapshot index di-mount secara langsung. Segment metadata dan data yang sering diakses disimpan di disk lokal (SSD), sementara segment dingin dibaca langsung dari Object Storage (Amazon S3 / GCS / Azure Blob) via blob range requests.
* **Frozen Tier:** Shard sepenuhnya reside di Object Storage. Cache lokal sangat minimal (hanya index structures/FST). Query dieksekusi secara asinkron dengan alokasi heap yang sangat efisien, mengorbankan latency pencarian demi densitas data tanpa batas.

### 3.3 Konsensus Raft Master Election & Pencegahan Split-Brain

Elasticsearch (versi 7.x+) meninggalkan `discovery.zen.minimum_master_nodes` dan beralih ke implementasi berbasis Raft consensus engine:
* Master election membutuhkan konfirmasi dari kuorum `(N/2) + 1` dari kumpulan node yang memiliki role `master`.
* Dalam arsitektur 2-Region atau Multi-AZ, kegagalan partisi jaringan dapat menyebabkan hilangnya kuorum jika node master terdistribusi secara genap.
* Implementasi enterprise menggunakan **Tiebreaker Node (Voting-Only Master Node)** di region/AZ independen (Region 3) untuk mempertahankan kuorum saat salah satu region utama terisolasi total.

---

## 4. Why & What

| Fitur | Apa Masalahnya? (Why) | Apa Solusinya? (What) | Dampak Bisnis / Teknis |
| :--- | :--- | :--- | :--- |
| **CCR (Cross-Cluster Replication)** | Replikasi storage tingkat SAN/LUN lambat, berisiko korupsi database, dan memicu *downtime* saat failover. | Replikasi asinkron tingkat shard logikal lintas cluster/region geografis yang berbeda. | RPO turun hingga level sub-detik (< 1s); arsitektur Active-Passive atau Local Read Replication. |
| **Searchable Snapshots** | Biaya penyimpanan SSD membengkak seiring bertambahnya retensi log audit dan compliance (misal: PCI-DSS 1 tahun). | Membaca data indeks langsung dari cloud object storage menggunakan cache lokal adaptif. | Penghematan biaya komputasi & disk hingga 60-80% tanpa perlu proses restore index manual. |
| **Document/Field Level Security** | Akses data multi-tenant atau data sensitif (PII, salary, medical) menuntut pemisahan indeks fisik secara masif. | Pembatasan akses baris (DLS) menggunakan Elasticsearch Query DSL dan pembatasan kolom (FLS) via Role RBAC. | Konsolidasi indeks (mengurangi shard overhead), segregasi data compliance (GDPR/UU PDP). |
| **Voting-Only Master** | Biaya node master penuh di availability zone ketiga tinggi hanya untuk bertindak sebagai arbitrase konsensus. | Master node yang berpartisipasi dalam voting kuorum pemilihan master namun tidak pernah dipilih menjadi master. | Menghindari split-brain multi-AZ dengan biaya resource komputasi minimal. |

---

## 5. How (Workflow Detail)

### Workflow Disaster Recovery Failover & Fallback dengan CCR

```
FASE 1: OPERASI NORMAL (Active-Passive)
[ Ingest Pipeline ] ──Writes──> [ Cluster Primary (DC-1) ]
                                         │ (CCR Sync: Sub-second)
                                         ▼
                                [ Cluster Standby (DC-2) ]
                                (Follower Index: Read-Only)

FASE 2: DISASTER PADA DC-1 (Disaster Event)
1. GSLB / API Gateway mendeteksi DC-1 Unhealthy (Healthcheck 3x berturut-turut gagal).
2. Otomasi Orchestrator menjalankan skrip failover:
   a. Pause replikasi CCR pada DC-2: POST /<follower_index>/_ccr/pause_follow
   b. Close follower index: POST /<follower_index>/_close
   c. Unfollow leader: POST /<follower_index>/_ccr/unfollow
   d. Open index (menjadi read-write normal index): POST /<follower_index>/_open
3. GSLB mengalihkan traffic ingest & search 100% ke DC-2.

FASE 3: FAILBACK & RESTORASI (DC-1 Pulih)
1. DC-1 hidup kembali; data yang tertinggal dikarantina.
2. Ingest tetap dialirkan ke DC-2 (sekarang menjadi Source of Truth).
3. DC-1 dijadikan follower dari DC-2:
   POST /<dc1_index>/_ccr/follow (Leader: DC-2).
4. Setelah sequence number sejajar (Lag = 0), traffic dialihkan kembali jika diinginkan.
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Logistik Pabrik Cetak dan Kurir Khusus
Bayangkan **Primary Cluster** adalah Kantor Pusat Percetakan yang mencetak buku dokumen secara terus-menerus. Setiap lembar diberi nomor urut unik tak terputus (*Sequence Number*).

* **CCR:** Bukan mengirim seluruh lemari buku secara fisik lewat kontainer laut (seperti backup snapshot lama), melainkan ada kurir khusus (*Follower Task*) yang duduk di kantor cabang, terus mencatat: *"Halaman terakhir yang saya fotokopi adalah nomor 400. Apakah ada nomor 401?"*. Kantor pusat menyimpan lembaran draf (*Soft Deletes*) sampai kurir mengonfirmasi lembaran tersebut sudah disalin ke kantor cabang.
* **Searchable Snapshots:** Seperti perpustakaan daerah yang hanya memajang katalog buku di rak display (*Metadata & Cache*). Buku aslinya tetap berada di gudang pusat (*S3 Storage*). Ketika ada pengunjung membaca bab tertentu, petugas mengambilkan halaman tersebut secara instan lewat jalur kilat, tanpa perlu memindahkan seisi perpustakaan ke meja baca.

### Diagram Arsitektur Multi-Region Active-Passive Production

```
                            [ GLOBAL DNS / GSLB ]
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            │ Health: OK                                        │ Health: Standby
            ▼                                                   ▼
┌───────────────────────────────┐                   ┌───────────────────────────────┐
│     REGION A (PRIMARY)        │                   │     REGION B (STANDBY)        │
│  ┌─────────────────────────┐  │                   │  ┌─────────────────────────┐  │
│  │   Master-01  Master-02  │  │                   │  │   Master-03  Master-04  │  │
│  └────────────┬────────────┘  │                   │  └────────────┬────────────┘  │
│               │               │                   │               │               │
│  ┌────────────▼────────────┐  │  CCR (mTLS/9300)  │  ┌────────────▼────────────┐  │
│  │ Data Hot/Warm Nodes     │──┼───────────────────┼─>│ Data Hot/Warm Nodes     │  │
│  │ (Index: logs-tx-001)    │  │                   │  │ (Index: logs-tx-001)    │  │
│  │ [Leader: Read-Write]    │  │                   │  │ [Follower: Read-Only]   │  │
│  └────────────┬────────────┘  │                   │  └────────────┬────────────┘  │
└───────────────┼───────────────┘                   └───────────────┼───────────────┘
                │                                                   │
                │        ┌─────────────────────────────────┐        │
                │        │     REGION C (TIEBREAKER)       │        │
                │        │  ┌───────────────────────────┐  │        │
                └───────>│  │ Master-05 (Voting-Only)   │  │<───────┘
                         │  └───────────────────────────┘  │
                         └─────────────────────────────────┘
                                         │
                         ┌───────────────▼─────────────────┐
                         │ Object Storage (S3 / Cold Tier) │
                         │   SLM Snapshots & Searchable    │
                         └─────────────────────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Konfigurasi Keamanan Role dengan Document & Field Level Security (DLS/FLS)

Skenario: Operator Call Center hanya diizinkan melihat data log transaksi milik regional mereka (`region_id == "ID-JKT"`), dan dilarang melihat nomor kartu kredit pelanggan (`credit_card_number`).

```json
POST /_security/role/callcenter_operator_jkt
{
  "indices": [
    {
      "names": [ "transactions-*" ],
      "privileges": [ "read" ],
      "field_security": {
        "grant": [ "transaction_id", "timestamp", "amount", "status", "customer_name" ],
        "except": [ "credit_card_number", "cvv" ]
      },
      "query": {
        "term": {
          "region_id": "ID-JKT"
        }
      }
    }
  ]
}
```

### 7.2 Practical Example: Enterprise Production Multi-Cluster CCR & SLM

#### Langkah 1: Setup Remote Cluster Connection (Dijalankan di Cluster Follower - DC-2)
Menggunakan secure sniff mode dengan TLS validation:

```json
PUT /_cluster/settings
{
  "persistent": {
    "cluster": {
      "remote": {
        "cluster_primary": {
          "seeds": [
            "10.100.1.10:9300",
            "10.100.1.11:9300",
            "10.100.1.12:9300"
          ],
          "skip_unavailable": false,
          "mode": "sniff"
        }
      }
    }
  }
}
```

Verifikasi status koneksi remote cluster:
```http
GET /_remote/info
```

#### Langkah 2: Buat Auto-Follow Pattern pada Cluster Follower (DC-2)
Pola ini secara otomatis mereplikasi semua indeks yang berawalan `banking-ledger-` dari cluster primary:

```json
PUT /_ccr/auto_follow/banking_ledger_autofollow_pattern
{
  "remote_cluster": "cluster_primary",
  "leader_index_patterns": [
    "banking-ledger-*"
  ],
  "follow_index_pattern": "{{leader_index}}-replicated",
  "settings": {
    "index.number_of_replicas": 2,
    "index.read_only": true
  },
  "max_read_request_operation_count": 5120,
  "max_outstanding_read_requests": 12,
  "max_read_request_size": "32mb",
  "max_write_request_operation_count": 5120,
  "max_write_request_size": "16mb",
  "max_outstanding_write_requests": 8,
  "max_write_buffer_count": 2147483647,
  "max_write_buffer_size": "512mb",
  "max_retry_delay": "500ms",
  "read_poll_timeout": "1m"
}
```

#### Langkah 3: Konfigurasi Snapshot Lifecycle Management (SLM) & Searchable Snapshots
Konfigurasi repository S3 di Cluster Leader:

```json
PUT /_snapshot/enterprise_s3_backup
{
  "type": "s3",
  "settings": {
    "bucket": "corp-es-snapshots-ap-southeast-1",
    "base_path": "production_core_cluster",
    "compress": true,
    "max_restore_bytes_per_sec": "100mb",
    "max_snapshot_bytes_per_sec": "100mb"
  }
}
```

Buat Policy SLM harian:
```json
PUT /_slm/policy/daily-cold-retention-policy
{
  "schedule": "0 30 1 * * ?",
  "name": "<daily-snap-{now/d}>",
  "repository": "enterprise_s3_backup",
  "config": {
    "indices": ["banking-ledger-*"],
    "ignore_unavailable": false,
    "include_global_state": true
  },
  "retention": {
    "expire_after": "365d",
    "min_count": 30,
    "max_count": 365
  }
}
```

Mount Snapshot sebagai Searchable Snapshot (Mount ke Cold Tier):
```json
POST /_snapshot/enterprise_s3_backup/daily-snap-2024.01.01/_mount?wait_for_completion=true
{
  "index": "banking-ledger-2024.01.01",
  "renamed_index": "restored-searchable-banking-ledger-2024.01.01",
  "index_settings": {
    "index.routing.allocation.include._tier_preference": "data_cold"
  },
  "storage": "shared_cache"
}
```

---

## 8. Real World Case Study

### Kasus: Sektor Finansial & Core Banking Gateway (Bank Skala Tier-1)

* **Skala Sistem:** 45 Node per cluster, 1.2 Petabyte data log transaksi finansial, 85.000 events/detik peak load.
* **Tantangan:** Regulasi otoritas moneter mengharuskan RPO $\le$ 3 detik dan RTO $\le$ 2 menit jika terjadi bencana total di Datacenter Utama (Jakarta DC-1). Cluster cadangan terletak di Surabaya (DC-2) dengan latensi jaringan (RTT WAN) 14 ms.
* **Insiden:** Terjadi *fiber cut* ganda dan kegagalan UPS di DC-1 yang merubuhkan seluruh power grid DC-1.

#### Solusi Arsitektur yang Diterapkan:
1. **CCR Asynchronous Topology:** Ingestion gateway (Logstash & Kafka) menggunakan local buffer di DC-1 dan DC-2. Di DC-1, indeks primer `tx-core-*` aktif ditulis, sementara DC-2 menjalankan CCR Auto-Follower pattern.
2. **Lag Management:** Dilakukan optimasi `read_poll_timeout` dan alokasi pipeline buffer CCR sehingga median replication delay terpantau di angka 280 milidetik (jauh di bawah limit RPO 3 detik).
3. **Automated Disaster Recovery Runbook:**
   Sistem orkestrator (HashiCorp Consul + Custom Python Failover Agent) mendeteksi kematian node DC-1 dalam 15 detik, memvalidasi hilangnya sinyal heartbeat, lalu mengeksekusi instruksi:

```bash
#!/usr/bin/env bash
set -eo pipefail

TARGET_CLUSTER="https://es-dc2.internal.bank:9200"
ES_AUTH="Authorization: ApiKey ${DISASTER_RECOVERY_KEY}"

echo "[DR-AGENT] Mengidentifikasi indeks follower CCR..."
FOLLOWERS=$(curl -s -k -H "${ES_AUTH}" "${TARGET_CLUSTER}/_ccr/info" | jq -r '.indices[].name')

for idx in ${FOLLOWERS}; do
  echo "[DR-AGENT] Menghentikan CCR follow pada index: ${idx}"
  curl -s -k -XPOST -H "${ES_AUTH}" "${TARGET_CLUSTER}/${idx}/_ccr/pause_follow"
  
  echo "[DR-AGENT] Menutup index untuk breaking dependency: ${idx}"
  curl -s -k -XPOST -H "${ES_AUTH}" "${TARGET_CLUSTER}/${idx}/_close"
  
  echo "[DR-AGENT] Memutus link replikasi (unfollow): ${idx}"
  curl -s -k -XPOST -H "${ES_AUTH}" "${TARGET_CLUSTER}/${idx}/_ccr/unfollow"
  
  echo "[DR-AGENT] Membuka kembali index sebagai Primary Read-Write: ${idx}"
  curl -s -k -XPOST -H "${ES_AUTH}" "${TARGET_CLUSTER}/${idx}/_open"
done

echo "[DR-AGENT] Update Core Routing DNS/Anycast ke DC-2..."
# Eksekusi migrasi traffic via DNS API Cloudflare/Route53
curl -s -X POST "https://api.dns-provider.com/v1/zones/failover" \
     -H "Authorization: Bearer ${DNS_TOKEN}" \
     -d '{"routing_policy": "FAILOVER_TO_DC2"}'

echo "[DR-AGENT] Failover berhasil diselesaikan."
```

* **Hasil Audit Pasca-Bencana:**
  * **RPO Aktual:** 0.42 detik (Data hilang hanya transaksi yang tertinggal dalam translog lokal DC-1 sesaat sebelum listrik putus total).
  * **RTO Aktual:** 48 detik (Di bawah batas 2 menit regulasi).
  * Tidak terjadi *split-brain* karena master DC-1 mati total dan master DC-2 berhasil mengamankan kuorum bersama Tiebreaker di Region Cloud (AWS Singapore).

---

## 9. Trade-offs

| Pendekatan / Fitur | Parameter | Konsekuensi Positif (Gain) | Konsekuensi Negatif (Cost/Pain) |
| :--- | :--- | :--- | :--- |
| **CCR vs Snapshot DR** | Latensi Failover | RTO hitungan detik; RPO sub-detik. | Membutuhkan resource komputasi & disk ganda yang menyala aktif di secondary cluster (Biaya compute 2x). |
| **Searchable Snapshots (Cold/Frozen)** | Biaya Penyimpanan | Memangkas biaya disk lokal hingga 80%; retensi tak terbatas. | Latensi query meningkat dari level milidetik (SSD) menjadi ratusan milidetik / detik (S3 latency). |
| **Document/Field Level Security (DLS/FLS)** | Keamanan Data | Isolasi data ketat dalam satu cluster tanpa fragmentasi index. | Penurunan throughput search 15-30% karena setiap shard request disisipi Lucene Filter query secara dinamis. |
| **mTLS Strict Verification** | Jaringan Inter-Node | Menutup celah Man-In-The-Middle dan impersonasi node tidak sah. | Beban negosiasi TLS handshake (CPU overhead), kompleksitas manajemen sertifikat (rotasi PKI berkala). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Retention Lease Kedaluwarsa (CCR Replication Broken)
* **Penyebab:** Terjadi network partition panjang antara DC-1 dan DC-2 yang melampaui `index.soft_deletes.retention_lease.period` (default 12 jam). Segment lama di leader sudah di-merge dan dihapus permanen.
* **Gejala:** Follower logs menampilkan error: `ShardFollowNodeTaskException: retention lease [...] not found`.
* **Solusi:**
  1. Hapus follower index: `DELETE /<follower_index>`
  2. Mulai ulang follow dari snapshot terbaru atau gunakan API follow manual dengan bootstrap snapshot baru:
     ```json
     PUT /<follower_index>/_ccr/follow
     {
       "remote_cluster": "cluster_primary",
       "leader_index": "<leader_index>"
     }
     ```
  3. Konfigurasi `index.soft_deletes.retention_lease.period: 72h` pada index template untuk sistem yang rentan degradasi jaringan WAN.

### 10.2 Kehilangan Master Quorum pada Topologi 2-Datacenter
* **Penyebab:** Memasang 2 Master di DC-1 dan 2 Master di DC-2 (Total 4 Master, Quorum butuh 3). Jika DC-1 putus, DC-2 hanya memiliki 2 node, sehingga gagal membentuk kuorum (`2 < 3`).
* **Gejala:** Muncul error `master_not_discovered_exception`. Cluster macet total dan menolak request write/read.
* **Solusi:** Jangan pernah membagi master node secara simetris di dua lokasi. Tambahkan 1 Node **Master Voting-Only** di lokasi ketiga (AZ independen / Cloud instance kecil).  
  Formula: `Quorum = (Total Master Nodes / 2) + 1`.

### 10.3 SSL/TLS Handshake Failure pada Remote Cluster Setup
* **Penyebab:** Certificate Authority (CA) yang digunakan untuk menandatangani sertifikat transport DC-1 tidak di-trust oleh keystore/truststore di DC-2.
* **Gejala:** Log error: `javax.net.ssl.SSLHandshakeException: PKIX path building failed`.
* **Solusi:** Import CA root dari DC-1 ke dalam truststore DC-2, dan sebaliknya (Cross-Signing atau gunakan satu Enterprise Root CA bersama).
  ```bash
  ./bin/elasticsearch-keystore add-file xpack.security.transport.ssl.truststore.secure_location /path/to/enterprise-root-ca.p12
  ```

---

## 11. Best Practices (Production Checklist)

### Arsitektur & Ketersediaan Jaringan (Resiliency)
- [ ] Shard Allocation Awareness diaktifkan pada deployment multi-AZ (`cluster.routing.allocation.awareness.attributes: zone`).
- [ ] Master Node ganjil (3 atau 5 node) dengan voting-only master di zona independen jika menggunakan arsitektur 2-DC.
- [ ] Nilai `cluster.remote.<alias>.transport.ping_schedule` diatur ke `5s` atau `10s` untuk menjaga koneksi stateful melalui firewall WAN.

### Enterprise Security
- [ ] `xpack.security.transport.ssl.verification_mode: full` (bukan `certificate` saja) untuk mencegah DNS spoofing antar node.
- [ ] Pisahkan HTTP Layer Port (9200) dari Transport Layer Port (9300). Transport layer tidak boleh diekspos keluar VPC/Private Network.
- [ ] Hindari penggunaan superuser `elastic` untuk integrasi runtime. Buat role terkecil (Principle of Least Privilege).
- [ ] Wajib masking atau enkripsi data sensitif di level ingestion sebelum masuk Lucene, kendati DLS/FLS aktif.

### Disaster Recovery & SLM
- [ ] Validasi integritas snapshot secara berkala dengan automated dry-run restore ke isolated test-cluster.
- [ ] Setting `indices.recovery.max_bytes_per_sec` disesuaikan dengan limit NIC bandwidth (contoh: `250mb` pada 10Gbps link) agar recovery/resync tidak mencekik traffic client.
- [ ] Simpan salinan KMS key atau snapshot credentials di luar cluster Elasticsearch untuk skenario break-glass recovery.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### File: `hands-on/m02/docker-compose.yml`
Menjalankan simulasi arsitektur multi-cluster: Cluster-A (Primary DC) dan Cluster-B (Follower DC) dalam satu overlay network yang terisolasi dengan TLS aktif.

```yaml
version: '3.8'

services:
  ca-cert-gen:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: ca-cert-gen
    user: "0"
    command: >
      bash -c '
        if [ ! -f /certs/elastic-stack-ca.p12 ]; then
          ./bin/elasticsearch-certutil ca --out /certs/elastic-stack-ca.p12 --pass ""
          ./bin/elasticsearch-certutil cert --ca /certs/elastic-stack-ca.p12 --ca-pass "" --out /certs/elastic-certificates.p12 --pass ""
        fi;
        chown -R 1000:0 /certs
      '
    volumes:
      - certs-data:/certs

  es-primary:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: es-primary
    depends_on:
      ca-cert-gen:
        condition: service_completed_successfully
    environment:
      - node.name=es-primary
      - cluster.name=cluster-primary
      - discovery.type=single-node
      - ELASTIC_PASSWORD=PrimarySuperSecretPass123!
      - xpack.security.enabled=true
      - xpack.security.transport.ssl.enabled=true
      - xpack.security.transport.ssl.verification_mode=certificate
      - xpack.security.transport.ssl.keystore.path=/usr/share/elasticsearch/config/certs/elastic-certificates.p12
      - xpack.security.transport.ssl.truststore.path=/usr/share/elasticsearch/config/certs/elastic-certificates.p12
      - xpack.security.http.ssl.enabled=false
    volumes:
      - certs-data:/usr/share/elasticsearch/config/certs
    ports:
      - "9201:9200"
      - "9301:9300"
    networks:
      es-dr-net:
        aliases:
          - es-primary.internal

  es-follower:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: es-follower
    depends_on:
      ca-cert-gen:
        condition: service_completed_successfully
    environment:
      - node.name=es-follower
      - cluster.name=cluster-follower
      - discovery.type=single-node
      - ELASTIC_PASSWORD=FollowerSuperSecretPass123!
      - xpack.security.enabled=true
      - xpack.security.transport.ssl.enabled=true
      - xpack.security.transport.ssl.verification_mode=certificate
      - xpack.security.transport.ssl.keystore.path=/usr/share/elasticsearch/config/certs/elastic-certificates.p12
      - xpack.security.transport.ssl.truststore.path=/usr/share/elasticsearch/config/certs/elastic-certificates.p12
      - xpack.security.http.ssl.enabled=false
    volumes:
      - certs-data:/usr/share/elasticsearch/config/certs
    ports:
      - "9202:9200"
      - "9302:9300"
    networks:
      es-dr-net:
        aliases:
          - es-follower.internal

volumes:
  certs-data:
    driver: local

networks:
  es-dr-net:
    driver: bridge
```

### File: `hands-on/m02/setup_and_verify.sh`
Skrip otomatis untuk menginisiasi CCR, memasukkan data, memverifikasi sinkronisasi, dan simulasi failover.

```bash
#!/usr/bin/env bash
set -euo pipefail

PRIMARY_URL="http://localhost:9201"
FOLLOWER_URL="http://localhost:9202"
AUTH_PRI="elastic:PrimarySuperSecretPass123!"
AUTH_FOL="elastic:FollowerSuperSecretPass123!"

echo ">>> 1. Menunggu kedua cluster siap..."
until curl -s -u "${AUTH_PRI}" "${PRIMARY_URL}/_cluster/health" | grep -q '"status":"green"\|"status":"yellow"'; do sleep 3; done
until curl -s -u "${AUTH_FOL}" "${FOLLOWER_URL}/_cluster/health" | grep -q '"status":"green"\|"status":"yellow"'; do sleep 3; done

echo ">>> 2. Konfigurasi Remote Connection pada Follower Cluster..."
curl -s -u "${AUTH_FOL}" -X PUT "${FOLLOWER_URL}/_cluster/settings" \
  -H 'Content-Type: application/json' -d'
{
  "persistent": {
    "cluster.remote": {
      "primary_cluster": {
        "seeds": ["es-primary.internal:9300"],
        "skip_unavailable": false
      }
    }
  }
}' | jq

echo ">>> 3. Membuat Leader Index di Primary..."
curl -s -u "${AUTH_PRI}" -X PUT "${PRIMARY_URL}/customer-transactions-2024" \
  -H 'Content-Type: application/json' -d'
{
  "settings": {
    "index.number_of_shards": 1,
    "index.number_of_replicas": 0,
    "index.soft_deletes.enabled": true
  },
  "mappings": {
    "properties": {
      "tx_id": { "type": "keyword" },
      "amount": { "type": "double" },
      "customer_tier": { "type": "keyword" }
    }
  }
}' | jq

echo ">>> 4. Ingest Sample Data ke Leader Index..."
for i in {1..5}; do
  curl -s -u "${AUTH_PRI}" -X POST "${PRIMARY_URL}/customer-transactions-2024/_doc" \
    -H 'Content-Type: application/json' -d"
  {
    \"tx_id\": \"TX-00$i\",
    \"amount\": $((i * 100)),
    \"customer_tier\": \"PLATINUM\"
  }" > /dev/null
done
curl -s -u "${AUTH_PRI}" -X POST "${PRIMARY_URL}/customer-transactions-2024/_refresh"

echo ">>> 5. Memulai Cross-Cluster Follower Index pada Follower Cluster..."
curl -s -u "${AUTH_FOL}" -X PUT "${FOLLOWER_URL}/customer-transactions-2024-replica/_ccr/follow?wait_for_active_shards=1" \
  -H 'Content-Type: application/json' -d'
{
  "remote_cluster": "primary_cluster",
  "leader_index": "customer-transactions-2024"
}' | jq

echo ">>> 6. Menunggu Replikasi Selesai & Validasi Record..."
sleep 4
DOC_COUNT_PRIMARY=$(curl -s -u "${AUTH_PRI}" "${PRIMARY_URL}/customer-transactions-2024/_count" | jq '.count')
DOC_COUNT_FOLLOWER=$(curl -s -u "${AUTH_FOL}" "${FOLLOWER_URL}/customer-transactions-2024-replica/_count" | jq '.count')

echo "Primary Doc Count: ${DOC_COUNT_PRIMARY}"
echo "Follower Doc Count: ${DOC_COUNT_FOLLOWER}"

if [ "${DOC_COUNT_PRIMARY}" -eq "${DOC_COUNT_FOLLOWER}" ]; then
  echo ">>> [SUKSES] Sinkronisasi CCR Berhasil Valid!"
else
  echo ">>> [GAGAL] Terjadi perbedaan data sinkronisasi!"
  exit 1
fi

echo ">>> 7. Menjalankan Simulasi Failover (Unfollow & Elevate to Leader)..."
curl -s -u "${AUTH_FOL}" -X POST "${FOLLOWER_URL}/customer-transactions-2024-replica/_ccr/pause_follow" | jq
curl -s -u "${AUTH_FOL}" -X POST "${FOLLOWER_URL}/customer-transactions-2024-replica/_close" | jq
curl -s -u "${AUTH_FOL}" -X POST "${FOLLOWER_URL}/customer-transactions-2024-replica/_ccr/unfollow" | jq
curl -s -u "${AUTH_FOL}" -X POST "${FOLLOWER_URL}/customer-transactions-2024-replica/_open" | jq

echo ">>> 8. Menguji Hak Tulis pada Index Eks-Follower..."
curl -s -u "${AUTH_FOL}" -X POST "${FOLLOWER_URL}/customer-transactions-2024-replica/_doc" \
  -H 'Content-Type: application/json' -d'{
    "tx_id": "TX-FAILOVER-001",
    "amount": 9999,
    "customer_tier": "EMERGENCY"
  }' | jq

echo ">>> Praktikum Selesai Sempurna."
```

---

## 13. Exercise

### Level Easy
1. Ubah parameter `read_poll_timeout` pada koneksi CCR agar lebih toleran terhadap latensi jaringan tinggi (misal: 2 menit).
2. Buat index pattern dengan fitur `soft_deletes` aktif dan tentukan masa retensi lease selama 48 jam. Tulis payload API request-nya.

### Level Medium
1. Konfigurasi Role Elasticsearch yang mengombinasikan **FLS** dan **DLS**:
   * Index: `audit-logs-*`
   * DLS: Hanya dokumen dengan `environment == "production"`.
   * FLS: Sembunyikan field `auth_token` dan `internal_ip`.
2. Lakukan simulasi network split pada praktikum: Jalankan perintah Docker network disconnect pada node Primary, verifikasi respon health node Follower, lalu eksekusi un-follow index secara manual via REST API.

### Level Hard
1. Buat skrip automasi (Python atau Bash) yang memonitor CCR replication lag via endpoint `GET /<follower_index>/_ccr/stats`. Jika `time_since_last_read_millis` melampaui ambang batas 5000ms selama 3 interval berturut-turut, picu alert webhook Slack dan simpan status diagnostic cluster ke dalam file dump.
2. Rancang template pemulihan fallback (Failback Scenario): Setelah primary cluster pulih, balik arah CCR sehingga primary cluster yang lama menjadi follower dari secondary cluster tanpa kehilangan data transaksi yang masuk selama disaster berlangsung.

---

## 14. Challenge

**Skenario Tantangan:**  
Perusahaan platform e-commerce FinTech multi-nasional menargetkan arsitektur data global dengan kriteria berikut:
1. Dua Datacenter Utama: Jakarta (Prod-JKT) dan Singapura (Prod-SGP).
2. Menggunakan topologi **Bi-directional Active-Active Read/Write Sharded CCR**:
   * Order untuk merchant Indonesia ditulis langsung ke `orders-id-*` di Prod-JKT dan di-replikasi ke Prod-SGP.
   * Order untuk merchant Singapura ditulis langsung ke `orders-sg-*` di Prod-SGP dan di-replikasi ke Prod-JKT.
3. Aplikasi di masing-masing region menggunakan **Cross-Cluster Search (CCS)** untuk melakukan analitik gabungan (`orders-id-*` dan `orders-sg-*`) secara lokal dengan latensi pembacaan di bawah 50 ms.
4. RPO maksimal adalah 0 detik untuk disaster lokal (AZ failure) dan $\le$ 2 detik untuk total catastrophe region disaster.
5. Anda dituntut untuk merancang:
   * Arsitektur pemetaan indeks, alias, dan topologi remote cluster.
   * Strategi penanganan UUID conflict antar cluster.
   * Penanganan skenario kegagalan: Jika Prod-JKT terbakar total, bagaimana skrip routing menulis order ID ke Prod-SGP tanpa menyebabkan tabrakan data saat Prod-JKT nantinya online kembali?

*Buat dokumen blueprint arsitektur yang mencakup diagram komponen, format JSON mapping/settings, dan SOP failback resolusi konflik tanpa menyebabkan duplicate write.*

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: 5 Pertanyaan Basic
1. Apa peran utama dari fitur *Soft Deletes* dalam arsitektur Cross-Cluster Replication (CCR)?
   * A. Menghapus field secara otomatis jika terkena proteksi FLS.
   * B. Mempertahankan riwayat operasi update/delete di level Lucene agar dapat dibaca follower sebelum di-purge oleh merge process.
   * C. Menghapus indeks yang tidak lagi memiliki master node aktif.
   * D. Mengurangi konsumsi memori heap pada data node.

2. Mengapa protokol transport port `9300` (bukan REST API port `9200`) yang digunakan untuk koneksi Cross-Cluster Replication?
   * A. Port 9300 menggunakan protokol serialisasi Java internal biner yang teroptimasi dengan throughput tinggi dan latensi rendah.
   * B. Port 9200 tidak mendukung enkripsi TLS.
   * C. Port 9300 merupakan standar HTTP/3 sedangkan 9200 masih HTTP/1.1.
   * D. Port 9200 hanya diperuntukkan untuk antarmuka Kibana.

3. Di tier manakah Searchable Snapshot paling tepat dialokasikan jika organisasi menginginkan biaya storage termurah dengan data yang jarang sekali dicari (hanya untuk kepatuhan hukum)?
   * A. Hot Tier
   * B. Warm Tier
   * C. Frozen Tier
   * D. Dedicated Master Tier

4. Berapa jumlah minimum node berstatus Master-eligible yang direkomendasikan pada arsitektur production cluster untuk menjamin toleransi kegagalan 1 master node?
   * A. 1
   * B. 2
   * C. 3
   * D. 4

5. Apa fungsi dari parameter `_ccr/unfollow` saat proses Disaster Recovery dijalankan?
   * A. Menghapus indeks yang ada di leader cluster.
   * B. Mengubah follower index yang read-only menjadi index reguler independen yang dapat menerima operasi penulisan (read-write).
   * C. Mengosongkan translog pada cluster follower.
   * D. Menghapus mapping index secara instan.

### Bagian 2: 5 Pertanyaan Intermediate
6. Jika cluster follower mengalami lag yang sangat jauh melebihi nilai `retention_lease.period`, apa yang akan terjadi secara internal pada follower shard?
   * A. Follower shard akan otomatis beralih ke REST polling.
   * B. Follower shard gagal melanjutkan replikasi (*replication halt*) dan masuk ke status error permanen hingga dilakukan inisialisasi ulang.
   * C. Leader cluster akan berhenti menerima penulisan data baru untuk menunggu follower.
   * D. Master node di follower cluster akan otomatis mengundurkan diri (demote).

7. Bagaimana cara kerja Document-Level Security (DLS) secara internal saat memproses request search?
   * A. Elasticsearch men-decrypt dokumen di memory, lalu menghapus dokumen yang dilarang.
   * B. Elasticsearch membungkus Lucene Query asli dengan Boolean Filter Query tambahan yang diturunkan dari definisi hak akses role.
   * C. Data node membaca seluruh dokumen dan membuang baris yang tidak sah di transport layer.
   * D. Inverted index dipisahkan secara fisik di disk per user.

8. Sebuah index mounted searchable snapshot pada *Cold Tier* memerlukan ruang penyimpanan lokal di disk node. Data apa saja yang disimpan pada disk lokal tersebut?
   * A. 100% data index sama seperti Hot tier.
   * B. Hanya inverted index, sedangkan document values dibuang.
   * C. Metadata indeks, struktur data esensial, dan cache dari segment-segment yang sering diakses (LRU cache).
   * D. File binary snapshot format `.tar.gz`.

9. Mengapa penambahan Voting-Only Master Node di region ketiga dapat mencegah Split-Brain pada dua datacenter utama?
   * A. Node tersebut selalu menjadi active master saat DC-1 mati.
   * B. Node tersebut menyediakan satu suara esensial untuk melengkapi kuorum `(N/2) + 1` tanpa membebani resource komputasi karena tidak memproses data atau menjadi master aktif.
   * C. Node tersebut mereplikasi semua translog secara real-time.
   * D. Node tersebut bertindak sebagai reverse proxy WAN.

10. Apa dampak performa utama dari mengaktifkan Field-Level Security (FLS) pada indeks dengan volume transaksi sangat tinggi?
    * A. Menghabiskan file descriptor hingga 100%.
    * B. Shard corruption saat proses merge segment.
    * C. Hilangnya kemampuan routing custom shard.
    * D. Peningkatan overhead CPU dan penurunan throughput karena setiap dokumen harus diparsing dan difilter field-nya sebelum serialisasi JSON dikirim ke client.

### Bagian 3: 3 Skenario Kasus Produksi
11. **Kasus 1:** Tim DevOps mengonfigurasi CCR antar-region. Indeks leader beroperasi normal, namun follower index terus menampilkan status `follower_indices_failed_to_track`. Saat dicek, throughput WAN sangat fluktuatif dan sesekali mengalami paket loss 1.5%. Pengaturan default apa yang harus di-tuning untuk menjaga stabilitas pipeline CCR pada koneksi WAN tersebut?
    * A. Mengurangi `max_read_request_size` dan meningkatkan `read_poll_timeout` serta `max_retry_delay`.
    * B. Mematikan fitur TLS transport layer.
    * C. Mengubah `number_of_shards` pada follower menjadi 10x lipat.
    * D. Mengganti JVM Heap size menjadi 64GB.

12. **Kasus 2:** Cluster Elasticsearch Anda mengalami split jaringan parsial (gray failure) di mana master node di AZ-A tidak dapat berkomunikasi dengan node data di AZ-B, tetapi AZ-C dapat melihat seluruh node. Traffic search mulai mengalami time-out berkala. Tindakan preventif apa di level arsitektur cluster settings yang dapat mempercepat deteksi node failure ini?
    * A. Mengaktifkan `cluster.fault_detection.follower_check.interval` dan mengatur `leader_check.timeout` ke level yang lebih agresif bersama mekanisme `transport.tracer`.
    * B. Menghapus konfigurasi Master-eligible di AZ-B.
    * C. Mematikan seluruh firewall antar-AZ tanpa verifikasi TLS.
    * D. Melakukan hard restart pada seluruh cluster secara serempak.

13. **Kasus 3:** Auditor PCI-DSS menemukan bahwa log pembayaran di Elasticsearch menyimpan nomor rekening bank. Anda harus membatasi agar developer hanya dapat melihat 4 digit terakhir nomor rekening (`acc_suffix`), sementara tim fraud investigation dapat membaca nomor rekening lengkap (`acc_number`). Bagaimana arsitektur solusi keamanan Elasticsearch yang paling optimal tanpa memecah indeks menjadi dua?
    * A. Mengonfigurasi dua Ingest Pipeline yang menduplikasi index menjadi `logs-dev` dan `logs-fraud`.
    * B. Menggunakan satu index bersama, mengonfigurasi FLS pada role developer (exclude field `acc_number`), dan memberikan full privilege role pada tim fraud, dipadukan dengan RBAC mapping.
    * C. Memasang Nginx reverse proxy di depan Elasticsearch untuk melakukan regex replace string secara dinamis.
    * D. Mengenkripsi disk menggunakan LUKS dan membagikan passphrase kepada tim fraud saja.

---

### Kunci Jawaban Evaluasi

#### Bagian 1: Basic
1. **B** — Soft deletes menahan segment Lucene yang telah di-delete/update agar tidak langsung dibuang saat background merge, sehingga follower memiliki window waktu untuk membaca delta perubahan via sequence numbers.
2. **A** — Transport Layer (9300) menggunakan internal Java serialization protocol yang jauh lebih efisien dibanding parsing JSON/HTTP pada port 9200.
3. **C** — Frozen Tier dirancang khusus untuk memotong biaya semaksimal mungkin dengan membaca data langsung dari object storage tanpa perlu reservasi local cache disk yang besar.
4. **C** — Diperlukan minimal 3 master-eligible nodes. Jika 1 mati, tersisa 2 node yang masih memenuhi kuorum `(3/2) + 1 = 2`.
5. **B** — Unfollow memutus status CCR task dan mengubah state follower index menjadi normal read-write index sehingga client dapat mengalirkan traffic penulisan secara langsung.

#### Bagian 2: Intermediate
6. **B** — Jika sequence number follower sudah tertinggal melewati batas soft deletes yang disimpan di leader (karena lease expired), follower tidak dapat melanjutkan sinkronisasi dan status CCR akan gagal permanen hingga di-bootstrap ulang.
7. **B** — DLS menyisipkan Lucene boolean filter query secara transparan di dalam Lucene core saat shard execution level, sehingga document yang tidak memenuhi kriteria query otomatis dilewati.
8. **C** — Cold Tier Searchable Snapshot mempertahankan struktur metadata, FST, dan cache lokal adaptif untuk data segment yang sering diakses guna menjaga latency tetap terkontrol.
9. **B** — Voting-only master node memiliki hak voting dalam konsensus Raft untuk membentuk kuorum, namun sistem tidak akan pernah menunjuk node ini sebagai active cluster state coordinator, memungkinkannya ditempatkan pada infrastruktur minim resource.
10. **D** — FLS mengevaluasi schema document sebelum membalas request ke client. Proses parsing, masking, dan re-serialisasi response payload membebani siklus CPU per request.

#### Bagian 3: Skenario Kasus Produksi
11. **A** — Menurunkan batch size (`max_read_request_size`) mencegah fragmentasi paket TCP pada link WAN yang tidak stabil, sedangkan meningkatkan `read_poll_timeout` dan `max_retry_delay` memberi ruang bagi koneksi untuk toleran terhadap spike latensi sesaat.
12. **A** — Penyesuaian fault detection parameter (`follower_check` dan `leader_check`) mempercepat cluster state publishing engine memutus node yang mengalami flaky connection sebelum menyebabkan search queue menumpuk.
13. **B** — FLS (Field-Level Security) yang dipadukan dengan Native RBAC merupakan solusi enterprise bawaan yang tidak membutuhkan duplikasi index storage fisik dan menghilangkan latensi perantara pihak ketiga.

---

## 16. Summary

1. **Cross-Cluster Replication (CCR):** Pondasi utama arsitektur multi-region enterprise untuk mencapai RPO sub-detik. Mekanisme ini bergantung pada *Soft Deletes*, *Retention Leases*, dan pelacakan *Sequence Numbers* melalui koneksi Transport TLS Port 9300.
2. **Disaster Recovery Strategy:** Transisi failover menuntut pemutusan rantai follower (`pause -> close -> unfollow -> open`) secara deterministik. Skrip orkestrasi otomatis terintegrasi dengan GSLB/DNS merupakan prasyarat mutlak untuk mencapai target RTO < 1 menit.
3. **Penyimpanan Ekonomis Melalui Searchable Snapshots:** Integrasi Snapshot Lifecycle Management (SLM) dengan Cold/Frozen tiers mengubah snapshot dari sekadar instrumen backup pasif menjadi data hidup yang dapat di-query secara langsung, menghemat konsumsi SSD performa tinggi hingga 80%.
4. **Zero-Trust Security:** Perlindungan data diatur secara berlapis: enkripsi data in-transit menggunakan mTLS strict verification, pencegahan unauthorized node injection via custom PKI, serta tata kelola data tenant menggunakan Field and Document-Level Security (FLS/DLS).
5. **Resiliency & Consensus:** Kuorum Raft `(N/2) + 1` mutlak dijaga dengan pembagian Master-Eligible Nodes yang asimetris atau pemanfaatan *Voting-Only Master Node* di zona tiebreaker independen guna mencegah skenario *Split-Brain*.