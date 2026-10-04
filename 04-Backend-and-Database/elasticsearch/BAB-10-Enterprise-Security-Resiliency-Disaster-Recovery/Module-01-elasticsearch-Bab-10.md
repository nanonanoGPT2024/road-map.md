# Bab 10 Module 01: Enterprise Security, Resiliency & Disaster Recovery

---

## 01: IDENTITAS MODUL
* **Track:** Backend and Database Infrastructure Engineering
* **Kategori:** 04-Backend-and-Database
* **Topik:** Elasticsearch Enterprise Operations
* **Modul:** Bab 10 Module 01: Enterprise Security, Resiliency & Disaster Recovery
* **Tingkat Kesulitan:** Advanced / Principal Engineer
* **Prasyarat:** Pemahaman arsitektur terdistribusi Elasticsearch (Cluster State, Shard Routing, Translog), Linux System Administration (systemd, OpenSSL, iptables), REST APIs, serta dasar-dasar TCP/IP Networking.

---

## 02: LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Mengonfigurasi arsitektur keamanan Zero-Trust pada cluster Elasticsearch multi-node: Transport TLS v1.3 (Node-to-Node mutual authentication) dan HTTP TLS menggunakan custom PKI.
2. Mengimplementasikan granular Role-Based Access Control (RBAC), Document-Level Security (DLS), dan Field-Level Security (FLS) untuk isolasi tenant.
3. Merancang topologi cluster multi-tier dengan shard allocation awareness lintas Availability Zone (AZ) untuk mencegah split-brain dan data loss.
4. Mengonfigurasi Snapshot Lifecycle Management (SLM) terotomasi ke cloud object storage (S3/GCS) lengkap dengan retention policy dan immutability.
5. Membangun strategi Active-Passive Cross-Cluster Replication (CCR) untuk disaster recovery antar-region dengan target RPO < 1 detik dan RTO < 5 menit.
6. Menganalisis dan memitigasi anomali replikasi, network partitioning, serta data corruption melalui verifikasi translog dan segment repair.

---

## 03: CONCEPT MAP DIAGRAM
```
+--------------------------------------------------------------------------------------------------+
|                            ENTERPRISE ELASTICSEARCH RESILIENCY ARCHITECTURE                      |
+--------------------------------------------------------------------------------------------------+
                                                 |
         +---------------------------------------+---------------------------------------+
         |                                                                               |
         v                                                                               v
+-------------------------------+                                       +-------------------------------+
|       PRIMARY REGION (AZ-A/B) |                                       |      DR REGION (AZ-C)         |
|  [Leader Cluster: prod-dc1]   |                                       |  [Follower Cluster: prod-dc2] |
|                               |                                       |                               |
|  +-------------------------+  |     Cross-Cluster Replication (CCR)   |  +-------------------------+  |
|  |       Zone Awareness    |  |======================================>|  |       Follower Shard    |  |
|  |  [AZ-A Node] [AZ-B Node]|  |    (Transport Port 9300 - TLS 1.3)    |  |   (Auto-Replication)    |  |
|  |   (Primary)    (Replica)|  |                                       |  +-------------------------+  |
|  +-------------------------+  |                                       +-------------------------------+
|               |               |                                                       |
|   Mutual TLS  | RBAC/DLS/FLS  |                                                       |
|   Encryption  | Tenant Sec    |                                                       |
|               v               |                                                       |
|  +-------------------------+  |        Snapshot Lifecycle Mgmt (SLM)                  |
|  | Secure Ingest Pipelines |  |-----------------------------------+                   |
|  +-------------------------+  |                                   |                   |
+-------------------------------+                                   |                   |
                                                                    v                   v
                                                +-----------------------------------------------+
                                                |     Encrypted S3 Glacier/GCS Object Storage   |
                                                |     (Immutable Snapshots / Versioning Locked) |
                                                +-----------------------------------------------+
```

---

## 04: MENGAPA RELEVAN
Di tingkat enterprise, kegagalan infrastruktur data bukan hanya masalah *downtime*, melainkan ancaman kepatuhan hukum (*regulatory compliance* seperti GDPR, HIPAA, PCI-DSS) dan integritas finansial. Data leakage melalui unencrypted transport layer, eksfiltrasi data antar-tenant dalam indeks gabungan, serta kehilangan data akibat degradasi *Availability Zone* (AZ) dapat menghancurkan kredibilitas perusahaan.

Arsitektur resilient modern menuntut:
* **Zero-Trust Data Plane:** Tidak ada komunikasi plaintext, baik antar node (*transport layer*) maupun dari klien (*HTTP REST layer*).
* **Guaranteed Continuity:** Kemampuan *failover* instan ketika satu data center down secara total tanpa kehilangan *unindexed translog operations*.
* **Strict Least Privilege:** Pembatasan akses hingga ke tingkat spesifik baris (*Document-Level*) dan kolom (*Field-Level*) langsung pada core engine database.

---

## 05: ANATOMI KONSEP INTI

### 1. Transport vs HTTP Layer Security
Elasticsearch menggunakan dua layer jaringan terpisah:
* **Transport Layer (Port 9300):** Komunikasi internal antar-node (Cluster State updates, shard replication, cross-node search scatter-gather). Menggunakan mutual TLS (mTLS) di mana setiap node memvalidasi sertifikat node lainnya.
* **HTTP Layer (Port 9200):** Komunikasi REST API dari klien (Logstash, Kibana, microservices). Menggunakan TLS standar dengan X.509 certificates yang divalidasi CA publik atau internal korporat.

### 2. DLS (Document-Level Security) & FLS (Field-Level Security)
DLS dan FLS diimplementasikan via Apache Lucene query rewriting saat fase eksekusi:
* **DLS:** Menginjeksi filter query ke dalam Lucene index reader sebelum *search phase* dijalankan. Jika tenant A mencari data, engine secara otomatis menambahkan `{"term": {"tenant_id": "tenant_A"}}` ke dalam *boolean must filter*.
* **FLS:** Mengeliminasi stored fields dan doc_values dari data projection pipe sebelum respons di-serialize ke JSON.

### 3. Shard Allocation Awareness
Mekanisme routing Lucene shard yang mencegah primary shard dan replica shard diletakkan pada domain kegagalan (failure domain) yang sama, seperti server rack, switch, atau AWS Availability Zone:
```properties
node.attr.zone: az-1
cluster.routing.allocation.awareness.attributes: zone
```

### 4. Cross-Cluster Replication (CCR) Engine
CCR beroperasi dengan model pull-based. Follower index pada cluster remote secara periodik mengambil (*pull*) operasi translog dari primary index pada cluster leader. 
* **Global Checkpoints:** Digunakan untuk melacak offset operasi Lucene yang telah berhasil ditulis dan disinkronkan di seluruh in-sync replica copies.
* **Auto-Follow Pattern:** Pola ekspresi reguler yang secara otomatis mengonfigurasi replikasi ketika index baru yang cocok dengan pola tersebut dibuat di leader cluster.

---

## 06: PANDUAN IMPLEMENTASI STEP-BY-STEP

### Langkah 1: Generate Enterprise PKI (Certificates)
Gunakan `elasticsearch-certutil` untuk membangun Certificate Authority (CA) internal dan sertifikat node dengan Subject Alternative Names (SAN) yang valid.

```bash
# 1. Buat direktori kerja PKI
mkdir -p /opt/es-pki && cd /opt/es-pki

# 2. Generate Certificate Authority (CA) privat
/usr/share/elasticsearch/bin/elasticsearch-certutil ca \
  --days 1095 \
  --out /opt/es-pki/elastic-ca.p12 \
  --pass ""

# 3. Buat file deklarasi instance
cat <<EOF > /opt/es-pki/instances.yml
instances:
  - name: "node-1"
    dns:
      - "node1.es.internal.corp"
      - "localhost"
    ip:
      - "10.0.10.11"
      - "127.0.0.1"
  - name: "node-2"
    dns:
      - "node2.es.internal.corp"
      - "localhost"
    ip:
      - "10.0.10.12"
      - "127.0.0.1"
EOF

# 4. Generate sertifikat berdasarkan deklarasi
/usr/share/elasticsearch/bin/elasticsearch-certutil cert \
  --ca /opt/es-pki/elastic-ca.p12 \
  --ca-pass "" \
  --in /opt/es-pki/instances.yml \
  --out /opt/es-pki/node-certs.zip \
  --pass ""

# 5. Ekstrak sertifikat
unzip /opt/es-pki/node-certs.zip -d /opt/es-pki/extracted/
```

### Langkah 2: Hardening `elasticsearch.yml` (TLS & Awareness)
Terapkan konfigurasi berikut pada **Node 1** (`/etc/elasticsearch/elasticsearch.yml`):

```yaml
cluster.name: enterprise-prod-cluster
node.name: node-1
node.roles: [ master, data, ingest ]
node.attr.zone: az-a

network.host: 10.0.10.11
http.port: 9200
transport.port: 9300

# High Availability Allocation Awareness
cluster.routing.allocation.awareness.attributes: zone

# Discovery & Bootstrap
discovery.seed_hosts: ["10.0.10.11:9300", "10.0.10.12:9300"]
cluster.initial_master_nodes: ["node-1", "node-2"]

# Security Layer - Enterprise Zero-Trust
xpack.security.enabled: true
xpack.security.enrollment.enabled: false

# Transport TLS (Mutual Authentication)
xpack.security.transport.ssl.enabled: true
xpack.security.transport.ssl.verification_mode: certificate
xpack.security.transport.ssl.keystore.path: /etc/elasticsearch/certs/node-1.p12
xpack.security.transport.ssl.truststore.path: /etc/elasticsearch/certs/node-1.p12
xpack.security.transport.ssl.supported_protocols: ["TLSv1.3", "TLSv1.2"]

# HTTP TLS
xpack.security.http.ssl.enabled: true
xpack.security.http.ssl.keystore.path: /etc/elasticsearch/certs/node-1.p12
xpack.security.http.ssl.truststore.path: /etc/elasticsearch/certs/node-1.p12
xpack.security.http.ssl.supported_protocols: ["TLSv1.3", "TLSv1.2"]
```

---

## 07: CONTOH KASUS SEDERHANA: Multi-Tenant DLS/FLS RBAC

Berikut konfigurasi murni via REST API untuk mengisolasi data tenant finansial, menyembunyikan nomor kartu kredit (`credit_card_number`), dan hanya mengizinkan akses ke dokumen transaksi milik tenant `ID_CORP_01`.

```http
### 1. Buat Role Tenant Khusus dengan DLS & FLS
POST /_security/role/finance_restricted_tenant_01
Host: 10.0.10.11:9200
Authorization: Basic ZWxhc3RpYzpwYXNzd29yZDEyMw==
Content-Type: application/json

{
  "cluster": ["monitor"],
  "indices": [
    {
      "names": ["transactions-*"],
      "privileges": ["read", "view_index_metadata"],
      "field_security": {
        "grant": ["transaction_id", "amount", "currency", "status", "tenant_id"]
      },
      "query": {
        "term": {
          "tenant_id": "ID_CORP_01"
        }
      }
    }
  ]
}

### 2. Buat Pengguna Aplikasi
POST /_security/user/app_finance_user
Host: 10.0.10.11:9200
Authorization: Basic ZWxhc3RpYzpwYXNzd29yZDEyMw==
Content-Type: application/json

{
  "password": "SecureEnterprisePassword2026!",
  "roles": ["finance_restricted_tenant_01"],
  "full_name": "Finance App System Account",
  "email": "finance-app@internal.corp"
}
```

---

## 08: IMPLEMENTASI PRODUCTION-GRADE LENGKAP KODE

### 1. Snapshot Repository S3 & SLM Policy
Jalankan script provisioning berikut untuk mengonfigurasi Snapshot Lifecycle Management (SLM) dengan storage enkripsi S3:

```bash
#!/usr/bin/env bash
set -euo pipefail

ES_HOST="https://10.0.10.11:9200"
ES_USER="elastic"
ES_PASS="SecureAdminPassword2026!"
CURL_FLAGS="--cacert /opt/es-pki/extracted/ca.crt -u ${ES_USER}:${ES_PASS} -s -f"

echo "[1/3] Mendaftarkan S3 Snapshot Repository..."
curl ${CURL_FLAGS} -X PUT "${ES_HOST}/_snapshot/aws_s3_cold_backup" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "s3",
    "settings": {
      "bucket": "prod-es-enterprise-snapshots-eu-central",
      "region": "eu-central-1",
      "base_path": "prod-dc1-cluster",
      "server_side_encryption": true,
      "storage_class": "intelligent_tiering",
      "compress": true,
      "max_snapshot_bytes_per_sec": "120mb"
    }
  }'

echo "[2/3] Menerapkan Snapshot Lifecycle Management (SLM) Policy..."
curl ${CURL_FLAGS} -X PUT "${ES_HOST}/_slm/policy/daily-production-snapshots" \
  -H "Content-Type: application/json" \
  -d '{
    "schedule": "0 30 1 * * ?", 
    "name": "<daily-snap-{now/d}>",
    "repository": "aws_s3_cold_backup",
    "config": {
      "indices": ["*"],
      "ignore_unavailable": false,
      "include_global_state": true
    },
    "retention": {
      "expire_after": "90d",
      "min_count": 7,
      "max_count": 120
    }
  }'

echo "[3/3] Menjalankan Snapshot Manual Awal..."
curl ${CURL_FLAGS} -X POST "${ES_HOST}/_slm/policy/daily-production-snapshots/_execute"
```

### 2. Cross-Cluster Replication (CCR) Setup
Jalankan pada **Follower Cluster (prod-dc2)** untuk menarik data dari **Leader Cluster (prod-dc1)**.

```http
### 1. Konfigurasi Remote Cluster Connection pada Follower Cluster
PUT /_cluster/settings
Host: 10.0.20.11:9200
Authorization: Basic ZWxhc3RpYzpwYXNzd29yZDEyMw==
Content-Type: application/json

{
  "persistent": {
    "cluster": {
      "remote": {
        "leader-dc1": {
          "seeds": ["10.0.10.11:9300", "10.0.10.12:9300"],
          "skip_unavailable": false
        }
      }
    }
  }
}

### 2. Buat Auto-Follow Pattern untuk Indeks Log dan Transaksi
PUT /_ccr/auto_follow/prod_metrics_replication
Host: 10.0.20.11:9200
Authorization: Basic ZWxhc3RpYzpwYXNzd29yZDEyMw==
Content-Type: application/json

{
  "remote_cluster": "leader-dc1",
  "leader_index_patterns": ["transactions-*", "logs-app-*"],
  "follow_index_pattern": "{{leader_index}}-follower",
  "settings": {
    "index.number_of_replicas": 1,
    "index.read_only": true
  },
  "max_outstanding_read_requests": 32,
  "max_outstanding_write_requests": 64,
  "max_read_request_size": "32mb",
  "max_write_request_size": "32mb"
}
```

---

## 09: DIAGRAM ALUR KERJA: Cross-Cluster Failover Lifecycle

```
Leader Cluster (prod-dc1)                 Follower Cluster (prod-dc2)
=========================                 ===========================
       |                                              |
 [Primary Shard]                                [Follower Shard]
       |                                              |
       |----- (1) Translog Write Sequence ----------->| (Pulls Checkpoints)
       |                                              |
  [CRASH: DC1 Offline]                                |
       X                                              |
                                                      | (2) Alerting Triggers Failover
                                                      v
                                        +-------------------------------+
                                        | (3) Pause Follower:           |
                                        | POST /<index>/_ccr/pause_follow
                                        +-------------------------------+
                                                      |
                                                      v
                                        +-------------------------------+
                                        | (4) Close Follower Index:     |
                                        | POST /<index>/_close          |
                                        +-------------------------------+
                                                      |
                                                      v
                                        +-------------------------------+
                                        | (5) Unfollow (Decouple):      |
                                        | POST /<index>/_ccr/unfollow   |
                                        +-------------------------------+
                                                      |
                                                      v
                                        +-------------------------------+
                                        | (6) Open as Standalone Write: |
                                        | POST /<index>/_open           |
                                        +-------------------------------+
                                                      |
                                                      v
                                        [Promoted to Primary Read/Write]
                                        Traffic rerouted via DNS/LB
```

---

## 10: ANALISIS TRADE-OFFS

| Pilihan Arsitektur | Keuntungan | Kerugian / Trade-off |
| :--- | :--- | :--- |
| **Active-Passive CCR** | RPO sangat rendah (<1 detik), performa read lokal di region DR. | Beban storage berlipat 2x, biaya transfer data lintas region (cross-AZ egress cost). |
| **Snapshot & Restore Only (SLM)** | Biaya penyimpanan sangat murah (S3 Glacier/Standard Object Store). | RPO lebih tinggi (sesuai interval snapshot, misal: 1 jam - 24 jam), RTO tinggi (waktu download index besar). |
| **Zone Allocation Awareness** | High Availability otomatis; tahan terhadap padamnya satu AZ data center. | Membutuhkan alokasi resource seimbang di semua AZ; query routing latency jika inter-AZ roundtrip tinggi. |
| **DLS & FLS Context** | Isolasi tenant sangat ketat langsung pada database engine, mempermudah compliance audit. | Penurunan throughput query hingga 15-25% karena overhead dynamic query rewriting dan hash evaluation. |

---

## 11: BEST PRACTICES & ANTIPATTERNS

### Best Practices
1. **Dedikasikan Dedicated Master Nodes:** Gunakan minimal 3 dedicated master-eligible nodes di 3 zona terpisah tanpa dibebani role data atau ingest.
2. **Aktifkan `cluster.routing.allocation.same_shard.host`:** Pastikan primary shard dan replica tidak pernah dialokasikan ke host fisik/VM yang sama.
3. **Konfigurasi Soft-Deletes:** Selalu aktifkan `index.soft_deletes.enabled: true` (default pada versi modern) untuk mempertahankan riwayat operasi Lucene yang krusial bagi stabilitas CCR.
4. **Enkripsi KeyStore:** Gunakan password pada `elasticsearch.keystore` saat menyimpan AWS Access Key / GCP Credentials.

### Antipatterns
1. **Shared Certificate Multi-Node:** Menggunakan sertifikat TLS liar (*wildcard certificate*) tanpa verifikasi *Subject Alternative Name* (SAN) atau IP binding antar node transport.
2. **Kombinasi Split-Brain Vulnerability:** Mengonfigurasi `discovery.seed_hosts` yang tidak mencakup semua master node yang sah, memicu segmentasi cluster saat partisi jaringan terjadi.
3. **Mengabaikan Translog Retention:** Menghapus translog secara agresif saat CCR aktif, menyebabkan follower kehilangan checkpoint dan jatuh ke status `circuit_breaking_exception` / error deserialisasi.

---

## 12: SECURITY HARDENING

### Linux Systemd Service Hardening
Amankan unit service Elasticsearch (`/etc/systemd/system/elasticsearch.service.d/override.conf`):

```ini
[Service]
# Proteksi Memory Paging
LimitMEMLOCK=infinity

# Proteksi File Descriptor
LimitNOFILE=65535

# Process Isolation Hardening
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ProtectKernelTunables=true
ProtectControlGroups=true
ReadWritePaths=/var/lib/elasticsearch /var/log/elasticsearch /etc/elasticsearch

# Restriksi Network Address Family
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
CapabilityBoundingSet=CAP_SYS_RESOURCE
```

### Script Otomasi RBAC Audit Verification
```bash
#!/bin/bash
# Validasi izin baca file keystore dan sertifikat
FILE_PATH="/etc/elasticsearch/certs/node-1.p12"
PERM=$(stat -c "%a" "$FILE_PATH")

if [ "$PERM" != "600" ] && [ "$PERM" != "400" ]; then
    echo "[CRITICAL] Izin sertifikat $FILE_PATH tidak aman: $PERM. Wajib 600 atau 400."
    chmod 600 "$FILE_PATH"
    chown elasticsearch:elasticsearch "$FILE_PATH"
    echo "[RESOLVED] Izin telah diperbaiki."
fi
```

---

## 13: OBSERVABILITAS & DEBUGGING

### Metrik Kritis Monitoring Resiliency
1. **CCR Sync Lag:** `elasticsearch.ccr.follower_indices.time_since_last_read_millis` (harus < 1000ms).
2. **Cluster Unassigned Shards:** `elasticsearch.cluster.unassigned_shards` (harus 0).
3. **SLM Snapshot Failure Count:** `elasticsearch.slm.snapshot_failed_count` (harus 0).

### Diagnostic Commands

```bash
# 1. Cek Status Shard Awareness dan Alokasi Tertahan
curl -s -k -u elastic:SecureAdminPassword2026 \
  "https://10.0.10.11:9200/_cluster/allocation/explain?pretty"

# 2. Cek Follower Shard Latency pada CCR
curl -s -k -u elastic:SecureAdminPassword2026 \
  "https://10.0.20.11:9200/_ccr/stats?pretty"

# 3. Validasi Keutuhan Snapshot SLM
curl -s -k -u elastic:SecureAdminPassword2026 \
  "https://10.0.10.11:9200/_slm/status?pretty"
```

---

## 14: BENCHMARKING & PERFORMANCE

Untuk mengukur dampak pengaktifan TLS 1.3 dan DLS/FLS terhadap cluster throughput, gunakan framework indexing load test sederhana berbasis `vegeta` atau `wrk` terhadap ingestion API.

### Script Load Testing HTTP Endpoint
```bash
#!/usr/bin/env bash
# Ingest baseline benchmark
cat <<EOF > target.json
POST https://10.0.10.11:9200/transactions-2026/_doc
Authorization: Basic YXBwX2ZpbmFuY2VfdXNlcjpTZWN1cmVFbnRlcnByaXNlUGFzc3dvcmQyMDI2IQ==
Content-Type: application/json

{"transaction_id": "TX9901", "amount": 1500.50, "currency": "EUR", "status": "CONFIRMED", "tenant_id": "ID_CORP_01", "credit_card_number": "4111-2222-3333-4444"}
EOF

# Jalankan 500 requests/sec selama 30 detik
echo "Running indexing load test under TLS + DLS/FLS rules..."
vegeta attack -rate=500 -duration=30s -targets=target.json -insecure | vegeta report
```

### Tuning CCR Throughput
Jika follower cluster mengalami bottle-necking pada cross-region link, tingkatkan setting konkurensi:

```http
PUT /transactions-follower/_ccr/following_index
Host: 10.0.20.11:9200
Authorization: Basic ZWxhc3RpYzpwYXNzd29yZDEyMw==
Content-Type: application/json

{
  "max_outstanding_read_requests": 64,
  "max_read_request_size": "64mb",
  "read_poll_timeout": "1m"
}
```

---

## 15: HANDS-ON LAB MINI-PROJECT: Zero-Data-Loss Failover Sim

### Objective
Mensimulasikan crash total cluster Primary (`leader-dc1`), lalu mengeksekusi failover runbook agar `follower-dc2` mengambil alih sebagai write-leader tanpa data loss.

### Instruksi Lab
1. **Langkah 1:** Buat follower index aktif via CCR di `prod-dc2`.
2. **Langkah 2:** Ingest 100 dokumen baru ke cluster leader di `prod-dc1`.
3. **Langkah 3:** Matikan service Elasticsearch pada `prod-dc1` (`systemctl stop elasticsearch`).
4. **Langkah 4:** Jalankan Failover Script di `prod-dc2`.

```bash
#!/usr/bin/env bash
set -euo pipefail
FOLLOWER_HOST="https://10.0.20.11:9200"
AUTH="-u elastic:SecureAdminPassword2026 --cacert /opt/es-pki/extracted/ca.crt"
INDEX="transactions-2026-follower"

echo "=== MEMULAI FAILOVER PROSES DI DC2 ==="

echo "[1/4] Pause Follower..."
curl -s -X POST $AUTH "$FOLLOWER_HOST/$INDEX/_ccr/pause_follow"

echo "[2/4] Close Index..."
curl -s -X POST $AUTH "$FOLLOWER_HOST/$INDEX/_close"

echo "[3/4] Unfollow Leader Index..."
curl -s -X POST $AUTH "$FOLLOWER_HOST/$INDEX/_ccr/unfollow"

echo "[4/4] Open Index as Standalone Leader..."
curl -s -X POST $AUTH "$FOLLOWER_HOST/$INDEX/_open"

echo "=== INDEX BERHASIL DIPROMOSIKAN JADI INDEPENDENT READ/WRITE ==="
```

---

## 16: AUTOMATED TESTING & VERIFICATION

Test suite berikut ditulis menggunakan Python (`pytest` + `requests`) untuk memvalidasi post-failover recovery dan kepatuhan isolasi RBAC DLS/FLS.

```python
import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LEADER_HOST = "https://10.0.10.11:9200"
FOLLOWER_HOST = "https://10.0.20.11:9200"
ADMIN_AUTH = ("elastic", "SecureAdminPassword2026!")
TENANT_USER_AUTH = ("app_finance_user", "SecureEnterprisePassword2026!")

def test_tenant_dls_isolation():
    """Memastikan bahwa app_finance_user HANYA bisa membaca tenant miliknya"""
    url = f"{LEADER_HOST}/transactions-*/_search"
    res = requests.get(url, auth=TENANT_USER_AUTH, verify=False)
    assert res.status_code == 200
    hits = res.json()["hits"]["hits"]
    
    for hit in hits:
        # Validasi DLS: Semua record harus ID_CORP_01
        assert hit["_source"]["tenant_id"] == "ID_CORP_01"
        # Validasi FLS: credit_card_number harus di-masking / tidak dikembalikan
        assert "credit_card_number" not in hit["_source"]

def test_ccr_replication_integrity():
    """Memastikan sinkronisasi dokumen antara leader dan follower match total hit-nya"""
    leader_res = requests.get(f"{LEADER_HOST}/transactions-*/_count", auth=ADMIN_AUTH, verify=False)
    follower_res = requests.get(f"{FOLLOWER_HOST}/transactions-*-follower/_count", auth=ADMIN_AUTH, verify=False)
    
    assert leader_res.status_code == 200
    assert follower_res.status_code == 200
    assert leader_res.json()["count"] == follower_res.json()["count"]
```

Eksekusi:
```bash
pytest test_es_security_dr.py -v
```

---

## 17: TROUBLESHOOTING GUIDE

| Gejala Masalah | Akar Penyebab (Root Cause) | Solusi Perbaikan |
| :--- | :--- | :--- |
| `SSLHandshakeException: Received fatal alert: certificate_unknown` | Node menggunakan certificate yang tidak ditandatangani oleh root CA yang sama di keystore. | Ekstrak kembali CA korporat, generate ulang sertifikat node via `elasticsearch-certutil`, dan perbarui `.p12` file di semua host. |
| `circuit_breaking_exception` pada Follower Cluster CCR | Ukuran batch CCR terlalu besar (`max_read_request_size`) menyebabkan JVM Old Gen heap saturation. | Kurangi `max_read_request_size` ke `8mb` dan `max_outstanding_read_requests` ke `16` pada follower index settings. |
| `illegal_argument_exception: cannot unfollow an active index` | Eksekusi command `_ccr/unfollow` dijalankan sebelum memanggil `_ccr/pause_follow` dan `_close`. | Ikuti runbook secara urut: 1. `pause_follow` -> 2. `_close` -> 3. `unfollow` -> 4. `_open`. |
| Shard unassigned: `awareness allocation failure` | Node pada salah satu AZ mati, dan alokasi shard dipaksa strictly balance (`forced_awareness`). | Tambahkan node pengganti pada AZ yang rusak atau hilangkan konfigurasi `forced_awareness` sementara pada cluster routing settings. |

---

## 18: CHECKLIST PRODUKSI

- [ ] **PKI Infrastructure:** Semua sertifikat Node dan Client memiliki validitas minimal 365 hari dengan auto-renewal alerts via Prometheus/Alertmanager.
- [ ] **Dedicated Master Nodes:** Tepat 3 Master Eligible nodes aktif di 3 zone independen dengan `node.roles: [ master ]`.
- [ ] **Keystore Secrets:** Tidak ada plaintext credentials di dalam file `elasticsearch.yml`. Semua kredensial S3/GCS berada di dalam `elasticsearch.keystore`.
- [ ] **CCR Auto-Follow Enabled:** Regex auto-follow aktif untuk seluruh index pattern yang bersifat business-critical.
- [ ] **Daily SLM Verified:** Snapshot lifecycle management telah teruji melakukan snapshot restore end-to-end setiap kuartal ke isolated staging cluster.
- [ ] **OS-Level Swappiness:** `vm.swappiness = 1` atau `bootstrap.memory_lock: true` aktif untuk mencegah swap disk latency degradation.
- [ ] **Granular Audit Logging:** `xpack.security.audit.enabled: true` diaktifkan dan dikirim ke cold storage terpisah untuk compliance retention.

---

## 19: RINGKASAN EKSEKUTIF
Modul ini merangkum postur ketahanan dan keamanan enterprise untuk arsitektur Elasticsearch. Fondasi dimulai dari implementasi sistem keamanan Zero-Trust yang mencakup TLS v1.3 transport level encryption, mutual node authentication, serta granular access governance melalui Document-Level Security (DLS) dan Field-Level Security (FLS).

Dari sisi ketahanan (resiliency) dan Disaster Recovery (DR), kombinasi zone awareness cluster routing, Snapshot Lifecycle Management (SLM) ke cloud object storage, serta Cross-Cluster Replication (CCR) Active-Passive menjamin perlindungan terhadap anomali di tingkat rack, subnet, maupun region failure. Dengan mengikuti arsitektur ini, sistem mampu mempertahankan integritas data operasional, memenuhi audit compliance, dan meminimalkan target RPO/RTO di bawah batas toleransi bisnis.

---

## 20: REFERENSI & BACAAN LANJUTAN
* Elastic NV. (2024). *Elasticsearch Reference: Secure the Elastic Stack*. Elastic Documentation.
* Elastic NV. (2024). *Cross-cluster replication and Disaster Recovery Architecture*. Elastic Reference Architecture Guides.
* Lucene Project. (2023). *Apache Lucene Core Documentation - Index Readers and Filter Rewrite Mechanics*. Apache Foundation.
* NIST Special Publication 800-52 Rev. 2. *Guidelines for the Selection, Configuration, and Use of Transport Layer Security (TLS) Implementations*.