# Kurikulum Enterprise Elasticsearch: Rekayasa Tingkat Lanjut
## Bab 07: Sharding, Scaling, & Routing Strategies
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Senior Software Engineer / Data Platform Architect diharapkan mampu:
1. **Menganalisis dan Membedah Algoritma Routing Internal**: Memahami matematika hashing Murmur3 dan distribusi partisi shard Lucene di level cluster state.
2. **Mendesain Strategi Custom Routing Skala Enterprise**: Mengeliminasi network latency dan bottleneck koordinasi query dengan beralih dari pola *Scatter-Gather* $O(N)$ ke *Direct Targeted Shard Execution* $O(1)$.
3. **Mencegah dan Menanggulangi Shard Hotspotting**: Mengimplementasikan `routing_partition_size` untuk tenant dengan volume data raksasa (*noisy neighbor/whale tenant*) tanpa mengorbankan isolasi data.
4. **Mengorkestrasi Topologi Shard Multiaz & Data Tiers**: Mengonfigurasi *Shard Allocation Awareness* dan *Forced Awareness* di seluruh Availability Zone (AZ) AWS/GCP, terintegrasi penuh dengan Index Lifecycle Management (ILM) berbasis Hot-Warm-Cold-Frozen.
5. **Melakukan Scaling Lifecycle Shard Secara Nirhenti (Zero-Downtime)**: Mengeksekusi API `_split`, `_shrink`, dan `_rollover` secara presisi menggunakan pipeline otomasi produksi.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
*   **Elasticsearch Core Architecture**: Perbedaan peran Master-eligible node, Data node, Coordinating node, dan Ingest node.
*   **Lucene Fundamentals**: Pemahaman tentang immutable segment, commit points, translog, dan proses segment merge (LSM-tree variant).
*   **Operating System & JVM**: Manajemen memory off-heap (OS Page Cache) vs on-heap (JVM Garbage Collection, CMS/G1GC/ZGC), serta network I/O buffering.
*   **Sistem Terdistribusi**: Pemahaman konsensus data, CAP theorem trade-offs, dan konsep consistent hashing / distributed hash tables (DHT).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Mekanisme Routing Internal dan Alokasi Shard
Secara internal, Elasticsearch memetakan setiap dokumen ke primary shard tertentu menggunakan hashing Murmur3. Formula matematis default alokasi dokumen ke shard adalah:

$$\text{shard\_num} = \left( | \text{Murmur3Hash}(\text{routing\_value}) | \pmod {\text{routing\_num\_shards}} \right) / \left( \frac{\text{routing\_num\_shards}}{\text{primary\_shards}} \right)$$

*Jika custom routing tidak didefinisikan, `routing_value` default adalah atribut metadata `_id` dokumen.*

Parameter `routing_num_shards` (default: diturunkan dari jumlah primary shards jika index di-split) bertindak sebagai *virtual shard address space*. Pendekatan ini memungkinkan operasi `_split` shard dilakukan tanpa perlu me-rehash seluruh dataset dari awal, menjaga integritas distribusi data ketika kapasitas scale-out bertambah.

```
+-----------------------------------------------------------------------------------+
|                            DOKUMEN: routing="tenant_A"                            |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
                      [ Murmur3 Hash Algorithm ] ──> Output: Int32 Hash Value
                                         │
                                         ▼
                  [ Modulo Virtual Shards: routing_num_shards ]
                                         │
                                         ▼
                  [ Integer Division: routing_num_shards / primary_shards ]
                                         │
                                         ▼
                                 Target: Shard 2
```

#### B. Custom Routing: Targeted Shard vs. Scatter-Gather
Dalam query standar tanpa custom routing, Coordinating Node harus menjalankan pola **Scatter-Gather**:
1. Coordinating node mengirimkan request query ke *setiap* shard di dalam index (satu copy per primary shard atau replikanya).
2. Setiap shard mengeksekusi pencarian lokal di level Lucene segment dan mengembalikan Priority Queue (misal: top 10 dokumen).
3. Coordinating node menggabungkan (*merge*) seluruh hasil dari semua shard, melakukan sorting global, dan mengekstrak dokumen yang relevan melalui fase fetch.

**Biaya Komputasi & Network Scatter-Gather:**
Jika index memiliki 100 primary shard, 1 query menghasilkan 100 network hop intra-cluster, 100 thread context switches di Data Nodes, dan overhead alokasi memory yang masif di Coordinating Node.

Sebaliknya, dengan **Custom Routing** (`_routing = tenant_id`):
Coordinating node menghitung hashing Murmur3 dari routing key secara instan, mengidentifikasi tepat 1 target shard, dan mengirimkan query langsung ke shard tersebut ($O(1)$ targeting).

```
Pola Scatter-Gather (Tanpa Routing):
Client ---> [Coordinating Node] ──┬──> [Shard 0] (Data Node 1)
                                  ├──> [Shard 1] (Data Node 2)
                                  ├──> [Shard 2] (Data Node 3)
                                  └──> [Shard N] (Data Node N)
Overhead: N network hops, N thread context-switches, Heavy memory merge.

Pola Custom Routing (Targeted):
Client ---> [Coordinating Node] ──────> [Shard 2] (Data Node 3)
Overhead: 1 network hop, isolasi penuh pada level shard.
```

#### C. Shard Allocation Deciders & Cluster State
Master node mengontrol penempatan shard ke node-node target menggunakan serangkaian rule logic yang disebut **Allocation Deciders**. Decider ini dievaluasi secara berurutan:
*   `DiskThresholdDecider`: Mencegah penempatan shard pada node yang melewati disk watermark (85% low, 90% high, 95% flood-stage).
*   `AwarenessAllocationDecider`: Memaksa shard replika dialokasikan ke zona fisik yang berbeda dari primary shard berdasarkan metadata hardware (`node.attr.zone`).
*   `FilterAllocationDecider`: Membatasi alokasi index hanya pada node dengan atribut tertentu (misal: `node.attr.tier: hot`).
*   `ThrottlerAllocationDecider`: Membatasi konkurensi recovery jaringan agar tidak menumbangkan performa I/O cluster.

---

### 4. Why & What

| Fitur / Pola | Mengapa Diperlukan (Why) | Apa Manfaatnya (What) |
| :--- | :--- | :--- |
| **Custom Routing** | Menghilangkan network amplification dan overhead CPU coordinating node saat volume query per detik (QPS) melonjak. | Mengubah search time latency dari multishard merge menjadi direct Lucene execution. QPS cluster naik hingga 10x-20x. |
| **Routing Partition Size** | Custom routing murni pada data multi-tenant ekstrem dapat menyebabkan 1 shard membesar tak terkendali (*hotspotting*). | Menyebarkan data dengan routing key yang sama ke sub-kelompok shard (*subset of shards*), memitigasi disk skew. |
| **Shard Allocation Awareness** | Mencegah downtime total saat satu Availability Zone (AZ) cloud provider mengalami pemadaman (*outage*). | Menjamin primary shard dan replica shard tidak pernah berada dalam fault domain fisik atau virtual yang sama. |
| **Shrink & Split API** | Penyesuaian kapasitas storage dan indexing throughput secara dinamis seiring berubahnya karakteristik data. | Shrink index usang untuk menghemat JVM heap overhead; Split index untuk menyerap load indexing masif. |

---

### 5. How (Workflow Detail)

#### Siklus Indexing dan Querying Berbasis Custom Routing

```
[CLIENT]
   │
   │ 1. Index Document (routing="enterprise_corp")
   ▼
[COORDINATING NODE]
   │
   │ 2. Hash murmur3("enterprise_corp")
   │ 3. Kalkulasi: Shard ID = 2
   ▼
[DATA NODE (Primary Shard 2)]
   │
   │ 4. Append Translog -> RAM Buffer (Lucene Inverted Index)
   │ 5. Asynchronous Replication via TCP
   ▼
[DATA NODE (Replica Shard 2)]
   │
   │ 6. Acknowledge Write
   ▼
[COORDINATING NODE] ──> [CLIENT] (Status: 201 Created)
```

```
[CLIENT]
   │
   │ 1. Search Query: GET /invoices/_search?routing=enterprise_corp
   ▼
[COORDINATING NODE]
   │
   │ 2. Evaluasi Hash Routing -> Target Langsung Shard 2
   ▼
[DATA NODE (Shard 2 Primary/Replica)]
   │
   │ 3. Eksekusi filter & query langsung pada Lucene Segments Shard 2
   │ 4. Ekstrak top-k dokumen dari priority queue lokal
   ▼
[COORDINATING NODE]
   │
   │ 5. Passthrough hasil (No cross-shard global merge overhead)
   ▼
[CLIENT] (Latency: <5ms)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kantor Pos Pusat vs. Lemari Arsip Khusus
Bayangkan perpustakaan raksasa dengan 100 lemari arsip (Shard). 
*   **Tanpa Custom Routing**: Ketika Anda mencari berkas "Invoice Perusahaan X", petugas perpustakaan (Coordinating Node) harus memanggil 100 asisten perpustakaan untuk membuka 100 lemari secara bersamaan, mencari arsip, lalu membawa semua berkas ke meja tengah untuk disortir kembali. Ini sangat boros tenaga dan membuat lorong perpustakaan macet total.
*   **Dengan Custom Routing**: Nama "Perusahaan X" secara instan diterjemahkan menjadi kode lemari: Lemari #42. Petugas langsung berjalan ke Lemari #42 tanpa melibatkan 99 lemari lainnya. Seluruh transaksi berjalan tenang, cepat, dan terisolasi.

#### Arsitektur Shard Allocation Awareness Multizona

```
+-----------------------------------------------------------------------------+
|                          AWS REGION: ap-southeast-1                         |
|                                                                             |
|  +--------------------------------+     +--------------------------------+  |
|  |     AVAILABILITY ZONE 1A       |     |     AVAILABILITY ZONE 1B       |  |
|  |     (node.attr.zone: az1)      |     |     (node.attr.zone: az2)      |  |
|  |                                |     |                                |  |
|  |  +--------------------------+  |     |  +--------------------------+  |  |
|  |  |      Data Node 01        |  |     |  |      Data Node 02        |  |  |
|  |  |  [Index A - Shard 0 (P)] |  |     |  |  [Index A - Shard 0 (R)] |  |  |
|  |  |  [Index A - Shard 1 (R)] |  |     |  |  [Index A - Shard 1 (P)] |  |  |
|  |  +--------------------------+  |     |  +--------------------------+  |  |
|  |                                |     |                                |  |
|  |  +--------------------------+  |     |  +--------------------------+  |  |
|  |  |      Data Node 03        |  |     |  |      Data Node 04        |  |  |
|  |  |  [Index B - Shard 0 (P)] |  |     |  |  [Index B - Shard 0 (R)] |  |  |
|  |  +--------------------------+  |     |  +--------------------------+  |  |
|  +--------------------------------+     +--------------------------------+  |
|                                  \       /                                  |
|                 Dedicated Cluster Cross-Connect Fiber                       |
+-----------------------------------------------------------------------------+
 * (P) = Primary Shard, (R) = Replica Shard.
 * Kegagalan total pada AZ 1A TIDAK menyebabkan data loss karena AZ 1B memegang 100% replica.
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Manual Custom Routing REST Calls

```http
### 1. Buat index dengan konfigurasi 3 shards
PUT /ecommerce_orders
{
  "settings": {
    "index": {
      "number_of_shards": 3,
      "number_of_replicas": 1
    }
  },
  "mappings": {
    "_routing": {
      "required": true
    },
    "properties": {
      "order_id": { "type": "keyword" },
      "customer_id": { "type": "keyword" },
      "total_amount": { "type": "scaled_float", "scaling_factor": 100 }
    }
  }
}

### 2. Index dokumen mewajibkan parameter routing
POST /ecommerce_orders/_doc/ord-1001?routing=cust-8899
{
  "order_id": "ord-1001",
  "customer_id": "cust-8899",
  "total_amount": 154000.50
}

### 3. Query dengan parameter routing (Hanya hit 1 shard)
GET /ecommerce_orders/_search?routing=cust-8899
{
  "query": {
    "match": {
      "order_id": "ord-1001"
    }
  }
}
```

#### B. Practical Enterprise Example: Component Templates, Partitioned Routing & Python High-Performance Pipeline

Konfigurasi index template dengan `routing_partition_size` untuk memitigasi *hotspotting* dari tenant masif:

```json
PUT /_index_template/b2b_saas_template
{
  "index_patterns": ["saas-ledger-*"],
  "template": {
    "settings": {
      "index.number_of_shards": 12,
      "index.number_of_replicas": 1,
      "index.routing_partition_size": 3,
      "index.routing.allocation.awareness.attributes": "zone",
      "index.lifecycle.name": "saas_ledger_policy",
      "index.lifecycle.rollover_alias": "saas-ledger-active"
    },
    "mappings": {
      "_routing": {
        "required": true
      },
      "properties": {
        "tenant_id": { "type": "keyword" },
        "transaction_id": { "type": "keyword" },
        "payload": { "type": "text" },
        "timestamp": { "type": "date" }
      }
    }
  }
}
```
*Catatan Arsitektur: Dengan `routing_partition_size: 3`, data untuk satu `tenant_id` akan didistribusikan ke dalam 3 shard (bukan terkunci di 1 shard tunggal), mencegah disk exhaustion jika satu tenant menghasilkan puluhan juta dokumen.*

Python Client Engine dengan Bulk Indexing Deterministic Routing:

```python
import hashlib
from elasticsearch import Elasticsearch, helpers
import sys

def get_elasticsearch_client() -> Elasticsearch:
    return Elasticsearch(
        ["https://es-node-01.internal.net:9200", "https://es-node-02.internal.net:9200"],
        basic_auth=("admin_platform", "SecretSecureProdVault123!"),
        verify_certs=True,
        ca_certs="/etc/ssl/certs/internal-ca.crt",
        max_retries=3,
        request_timeout=30
    )

def generate_bulk_actions(batch_data: list[dict]):
    for entry in batch_data:
        # Menggunakan tenant_id secara eksplisit sebagai routing key
        yield {
            "_op_type": "index",
            "_index": "saas-ledger-active",
            "_id": entry["transaction_id"],
            "routing": entry["tenant_id"],
            "_source": {
                "tenant_id": entry["tenant_id"],
                "transaction_id": entry["transaction_id"],
                "payload": entry["payload"],
                "timestamp": entry["timestamp"]
            }
        }

def execute_ingestion(es: Elasticsearch, records: list[dict]):
    try:
        success, failed = helpers.bulk(
            es,
            generate_bulk_actions(records),
            chunk_size=1000,
            raise_on_error=False,
            stats_only=False
        )
        if failed:
            print(f"[ALERT] Operasi bulk mendeteksi {len(failed)} kegagalan dokumen.", file=sys.stderr)
        print(f"[INFO] Berhasil melakukan ingest {success} dokumen dengan targeted routing.")
    except Exception as exc:
        print(f"[CRITICAL] Bulk Ingestion Pipeline Terhenti: {str(exc)}", file=sys.stderr)
        raise exc

if __name__ == "__main__":
    client = get_elasticsearch_client()
    dummy_payload = [
        {
            "tenant_id": f"org_idx_{i % 5}",
            "transaction_id": f"txn_{100000 + i}",
            "payload": f"Audit trace event {i}",
            "timestamp": "2026-03-30T10:00:00Z"
        }
        for i in range(5000)
    ]
    execute_ingestion(client, dummy_payload)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Multi-Tenant B2B Omnichannel Fintech Engine
*   **Skala Data**: 80.000 Tenant Korporat, 1,5 Miliar Transaksi Bulanan, Total Storage: 45 TB.
*   **Masalah Awal**:
    *   Query SLA P99 hancur di level **8,2 detik** saat jam sibuk pasar (09:00 - 15:00).
    *   Cluster sering mengalami `OutOfMemoryError` (OOM) pada Coordinating Node akibat Scatter-Gather di index bulanan yang memiliki 30 primary shard.
    *   Satu tenant raksasa (*Whale Tenant* - mencakup 35% total transaksi nasional) memicu *disk skew* parah: Node 4 terisi 92% (Watermark Flood-Stage terpicu), sementara Node 1-3 hanya terisi 30%.
*   **Solusi Rekayasa**:
    1.  **Refactoring Routing**: Terapkan `_routing = tenant_id` dengan `routing_partition_size: 4`. Pendekatan ini membagi data tenant raksasa ke 4 shard, menjaga utilisasi resource merata.
    2.  **Topologi Tiering + Rollover**: Sharding dinamis via ILM Rollover setiap 35GB atau umur 7 hari.
    3.  **Strict Routing Enforcement**: Setting mappings `"dynamic": "strict"` dan `"_routing": { "required": true }`.
*   **Hasil Evaluasi**:
    *   P99 Query Latency anjlok dari **8.200 ms** menjadi **34 ms** (penurunan lebih dari 99%).
    *   Beban memory pada Coordinating Node turun sebesar **78%** karena eliminasi array merge lintas puluhan shard.
    *   Disk skew antar node data turun dari deviasi 62% menjadi kurang dari 7%.

---

### 9. Trade-offs

| Pendekatan | Keuntungan Utama | Kerugian / Risiko | Biaya Operasional & Mitigasi |
| :--- | :--- | :--- | :--- |
| **Custom Routing Murni (`routing=tenant_id`)** | Throughput pencarian melonjak drastis, eliminasi overhead scatter-gather. | Risiko fatal *Data Skew*: Tenant raksasa membuat 1 shard menjadi sangat besar (*hotspot*). | Mitigasi: Terapkan `index.routing_partition_size` untuk membagi data tenant ke subset shards. |
| **Banyak Shard Kecil (<10GB per shard)** | Indexing parallelization sangat cepat, proses recovery file shard antar-node singkat. | *Over-sharding*: Lucene segment metadata menghabiskan JVM Heap; cluster state menjadi lambat disinkronisasi. | Batasi total primary & replica shard maksimal 20 shard per 1 GB JVM Heap Data Node. |
| **Shard Ukuran Masif (>50GB per shard)** | Menghemat alokasi memory JVM cluster; efisiensi kompresi segment lebih optimal. | Pemulihan node (*peer recovery*) sangat lambat, resync network tersendat, pemindahan shard timeout. | Batasi ukuran shard data log/time-series maksimal 50GB; data search/latency-critical maksimal 30GB. |
| **Multi-AZ Shard Awareness** | High Availability kelas enterprise; cluster tahan terhadap pemadaman total satu data center. | Trafik indexing cross-AZ dikenakan biaya data transfer cloud (misal: AWS Cross-AZ Data Fee). | Justifikasi biaya infrastruktur dengan metrik SLA uptime business 99.99%. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Mengabaikan Routing Parameter pada Query
*Gejala*: Aplikasi indexing menggunakan custom routing, tetapi tim frontend/backend melakukan query tanpa menyertakan `?routing=...` pada HTTP call.
*Dampak*: Query mengeksekusi scatter-gather ke seluruh shard tanpa optimasi.
*Solusi*: Wajibkan validasi routing via backend layer atau buat query validation middleware.

#### 2. Shard Allocation Terjebak (*Unassigned Shards*)
*Investigasi*:
Gunakan Cluster Allocation Explain API secara presisi:
```json
POST /_cluster/allocation/explain
{
  "index": "saas-ledger-2026.03.30-000001",
  "shard": 0,
  "primary": false
}
```
*Interpretasi Output*:
Cari blok `decider_enforcement`:
*   Jika `awareness_allocation_decider: NO`: Semua node di availability zone yang sama sudah memegang replica atau primary. Solusi: Scale node di zona target.
*   Jika `disk_threshold_decider: NO`: Node target telah melampaui disk high watermark (90%). Segera bersihkan log atau scale block storage (EBS/Persistent Disk).

#### 3. Thread Pool Rejection (`es_rejected_execution_exception`)
*Akar Masalah*: Lonjakan antrean query/indexing karena scatter-gather menghabiskan thread pool `search` atau `write`.
*Command Debugging*:
```bash
GET /_cat/thread_pool/search?v=true&h=node_name,name,active,rejected,completed,queue
```
Jika `rejected` bernilai > 0 secara konsisten, Anda mengalami bottleneck scatter-gather atau undersized thread pool capacity.

---

### 11. Best Practices (Production Checklist)

* [ ] **Shard Sizing Rule of Thumb**:
    * Log / Observabilitas / Time-series: Targetkan ukuran per shard antara **30 GB - 50 GB**.
    * Latency-sensitive Search / Retail App: Targetkan ukuran per shard antara **10 GB - 25 GB**.
* [ ] **Rasio JVM Heap terhadap Shard**: Pastikan jumlah shard aktif di satu node tidak melebihi **20 shard per 1 GB heap** (Contoh: Node dengan JVM Heap 31 GB maksimal memegang 600 shard).
* [ ] **Wajibkan Custom Routing**: Tambahkan `"_routing": { "required": true }` pada skema mapping untuk mencegah developer meng-index data tanpa routing key.
* [ ] **Gunakan Routing Partition Size**: Jika variasi volume data antar key berbeda lebih dari 100x lipat, aktifkan `routing_partition_size` (nilai ideal: 2 hingga 5).
* [ ] **Konfigurasi Zone Awareness Wajib**: Definisikan `cluster.routing.allocation.awareness.attributes: "zone"` di `elasticsearch.yml` dan konfigurasikan setiap node dengan `node.attr.zone: az-1`, `node.attr.zone: az-2`.
* [ ] **Shard Max JVM Constraint**: Jangan pernah memberikan JVM Heap lebih besar dari **31.5 GB** untuk menghindari rusaknya optimasi *Compressed Ordinary Object Pointers (Compressed OOPs)*.

---

### 12. Hands-on Practice

Buat seluruh lingkungan praktikum di direktori `hands-on/m02/`.

#### Langkah 1: Siapkan Orchestration Multi-Node Cluster Multi-AZ
Simpan file berikut sebagai `hands-on/m02/docker-compose.yml`:

```yaml
version: '3.8'
services:
  es-master:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    container_name: es-master
    environment:
      - node.name=es-master
      - cluster.name=enterprise-cluster
      - node.roles=master
      - cluster.initial_master_nodes=es-master
      - discovery.seed_hosts=es-data-az1,es-data-az2
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    networks:
      - es-network

  es-data-az1:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    container_name: es-data-az1
    environment:
      - node.name=es-data-az1
      - cluster.name=enterprise-cluster
      - node.roles=data
      - node.attr.zone=az-1
      - discovery.seed_hosts=es-master
      - cluster.routing.allocation.awareness.attributes=zone
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
    networks:
      - es-network

  es-data-az2:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    container_name: es-data-az2
    environment:
      - node.name=es-data-az2
      - cluster.name=enterprise-cluster
      - node.roles=data
      - node.attr.zone=az-2
      - discovery.seed_hosts=es-master
      - cluster.routing.allocation.awareness.attributes=zone
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
    networks:
      - es-network

networks:
  es-network:
    driver: bridge
```

Jalankan cluster:
```bash
docker compose -f hands-on/m02/docker-compose.yml up -d
```

#### Langkah 2: Buat Pipeline Automasi & Index Template
Buat file script `hands-on/m02/setup_environment.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ES_URL="http://localhost:9200"

echo "[1/4] Menunggu Cluster Berstatus Green/Yellow..."
until curl -s "${ES_URL}/_cluster/health" | grep -q '"status":"yellow"\|"status":"green"'; do
    sleep 2
done

echo "[2/4] Menerapkan Cluster Shard Awareness Global..."
curl -X PUT "${ES_URL}/_cluster/settings" -H 'Content-Type: application/json' -d'
{
  "persistent": {
    "cluster.routing.allocation.awareness.attributes": "zone"
  }
}'

echo -e "\n[3/4] Mendaftarkan Index Template dengan Custom Routing Wajib..."
curl -X PUT "${ES_URL}/_index_template/tenant_data_template" -H 'Content-Type: application/json' -d'
{
  "index_patterns": ["tenant-store-*"],
  "template": {
    "settings": {
      "index.number_of_shards": 4,
      "index.number_of_replicas": 1
    },
    "mappings": {
      "_routing": {
        "required": true
      },
      "properties": {
        "account_id": { "type": "keyword" },
        "invoice_num": { "type": "keyword" },
        "amount": { "type": "double" }
      }
    }
  }
}'

echo -e "\n[4/4] Inisialisasi Index Baru..."
curl -X PUT "${ES_URL}/tenant-store-prod-001"
echo -e "\nSetup Selesai Secara Sukses!"
```
Eksekusi:
```bash
chmod +x hands-on/m02/setup_environment.sh
./hands-on/m02/setup_environment.sh
```

#### Langkah 3: Eksekusi Targeted Profiling & Evaluasi Shard Hit
Buat script query tester `hands-on/m02/verify_routing.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
ES_URL="http://localhost:9200"

echo "[1] Melakukan Indexing Data..."
curl -s -X POST "${ES_URL}/tenant-store-prod-001/_doc/1?routing=client_acme" -H 'Content-Type: application/json' -d'
{"account_id": "client_acme", "invoice_num": "INV-001", "amount": 2500.0}'

curl -s -X POST "${ES_URL}/tenant-store-prod-001/_doc/2?routing=client_globex" -H 'Content-Type: application/json' -d'
{"account_id": "client_globex", "invoice_num": "INV-002", "amount": 9900.0}'

echo -e "\n[2] Menjalankan Force Flush/Refresh..."
curl -s -X POST "${ES_URL}/tenant-store-prod-001/_refresh"

echo -e "\n[3] Analisis Query EXPLAIN Tanpa Routing (Menghantam 4 Shards):"
curl -s -X GET "${ES_URL}/tenant-store-prod-001/_search" -H 'Content-Type: application/json' -d'
{"query": {"match_all": {}}}' | jq '._shards'

echo -e "\n[4] Analisis Query EXPLAIN Dengan Custom Routing (Hanya Menghantam 1 Shard):"
curl -s -X GET "${ES_URL}/tenant-store-prod-001/_search?routing=client_acme" -H 'Content-Type: application/json' -d'
{"query": {"match_all": {}}}' | jq '._shards'
```
Eksekusi:
```bash
chmod +x hands-on/m02/verify_routing.sh
./hands-on/m02/verify_routing.sh
```

*Amati output JSON `_shards`*: Query dengan `routing=client_acme` akan menampilkan `"total": 1`, membuktikan query hanya menyasar single targeted shard.

---

### 13. Exercise

#### Level: Easy
1. Dari output berikut: Dokumen di-index dengan routing key `"alpha"`. Jika cluster memiliki index dengan 5 primary shards, hitung secara konseptual mengapa Murmur3 hash memastikan dokumen selalu mendarat pada shard yang sama jika jumlah shard tidak berubah.
2. Buat REST call sederhana untuk mengubah index `log-audit` yang ada agar menolak semua penulisan dokumen baru jika tidak menyertakan custom routing.

#### Level: Medium
1. Konfigurasikan template index di mana dokumen menggunakan routing partition. Berikan setting JSON lengkap untuk index dengan 10 primary shard, dan `routing_partition_size` bernilai 2.
2. Tulis curl command untuk menjalankan `_shrink` API untuk mengubah index bernama `telemetry-october` dari 8 primary shard menjadi 2 primary shard. Sebutkan prasyarat status replica dan read-only yang wajib dipenuhi sebelum proses shrink dieksekusi.

#### Level: Hard
1. Desain skenario migrasi langsung (Zero Downtime) untuk index produksi `core-banking` sebesar 1.8 TB yang awalnya dibuat **tanpa routing** (30 shards), diubah menjadi index baru yang **mewajibkan routing berbasis `merchant_id`** (10 shards dengan awareness 2 availability zone).
2. Tulis script automasi menggunakan Bash / Python yang:
    * Membuat index target dengan spesifikasi routing yang benar.
    * Menginisialisasi `_reindex` API secara async dengan re-routing script.
    * Memantau `_tasks` API hingga selesai.
    * Mengalihkan Index Alias secara atomik (`atomic alias swap`).

---

### 14. Challenge

**Skenario**: Anda adalah Principal Architect di perusahaan ride-hailing & delivery raksasa. Sistem memiliki 1 index aktif untuk order tracking (`orders-active`).
*   **Karakteristik Data**: 95% merchant berskala mikro/kecil (hanya menghasilkan puluhan order per hari). Namun, ada 5 partner waralaba internasional (Whale Tenants) yang masing-masing menyumbang 10 juta order per hari.
*   **Kendala**:
    *   Jika menggunakan `routing = merchant_id` murni, node yang menampung primary shard untuk 5 tenant besar tersebut langsung mengalami kehabisan disk dan CPU throttled.
    *   Jika tidak menggunakan routing sama sekali, throughput sistem drop drastis karena P99 search latency melonjak ketika 10.000 driver memeriksa order secara serentak (Scatter-Gather bottleneck).
    *   Penggunaan `routing_partition_size` berlaku secara seragam untuk seluruh index. Jika Anda mengeset partition size terlalu besar, tenant kecil akan tersebar dan menaikkan latency.

**Misi Anda**:
Rancang arsitektur routing dan sharding adaptif yang menyelesaikan anomali ini.
1. Bagaimana Anda memisahkan atau memetakan skema routing untuk *Whale Tenant* vs *Micro Tenant*?
2. Bagaimana desain routing key (`<merchant_id>_<date>` vs custom hash salt) untuk memecah data whale tenant tanpa mengubah arsitektur kode frontend?
3. Buktikan secara teoritis bagaimana skema Anda mencegah pembengkakan shard melebihi batasan 50GB per Lucene shard dan menjamin pencarian tetap efisien!

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic (5 Pertanyaan)
1. Algoritma default apa yang digunakan Elasticsearch untuk menghitung mapping primary shard dari suatu routing key?
   * A. MD5
   * B. SHA-256
   * C. Murmur3
   * D. CRC32
2. Berapa target ukuran shard (*shard size*) yang direkomendasikan secara umum untuk data search-heavy/latency-critical?
   * A. 100 GB - 200 GB
   * B. 10 GB - 25 GB
   * C. 500 MB - 1 GB
   * D. Tepat 100 MB
3. Parameter apa yang harus diset menjadi `true` dalam mapping agar Elasticsearch menolak dokumen yang di-index tanpa routing key?
   * A. `_routing.force_enable`
   * B. `index.enforce_routing`
   * C. `_routing.required`
   * D. `cluster.routing.strict`
4. Berapa batas maksimum JVM Heap yang sangat disarankan untuk Data Node Elasticsearch agar Compressed OOPs tetap aktif?
   * A. 64 GB
   * B. Sekitar 31.5 GB
   * C. 128 GB
   * D. 16 GB
5. Operasi API mana yang dapat digunakan untuk menggabungkan primary shards dari sebuah index yang sudah read-only menjadi jumlah shard yang lebih sedikit?
   * A. `_split`
   * B. `_rollover`
   * C. `_shrink`
   * D. `_merge`

#### B. Intermediate (5 Pertanyaan)
6. Jika sebuah index dikonfigurasi dengan `index.routing_partition_size: 3` dan memiliki `number_of_shards: 9`, apa yang terjadi saat query dijalankan dengan menyertakan single custom routing key?
   * A. Query hanya memeriksa 1 shard.
   * B. Query memeriksa seluruh 9 shard.
   * C. Query memeriksa tepat 3 shard yang menjadi subset hash dari key tersebut.
   * D. Elasticsearch menghasilkan error `IllegalPartitionSizeException`.
7. Mengapa over-sharding (memiliki ribuan shard berukuran kecil, misal <1GB) dapat merusak performa cluster secara signifikan?
   * A. Karena hard disk tidak bisa membaca file kecil.
   * B. Karena setiap shard Lucene memakan overhead heap untuk segment metadata, memicu tekanan GC dan membebani Master Node dalam sinkronisasi Cluster State.
   * C. Shard kecil otomatis mematikan fitur Lucene doc values.
   * D. Karena IOPS SSD otomatis turun secara drastis saat membaca shard kecil.
8. Apa fungsi utama dari setting `cluster.routing.allocation.awareness.attributes`?
   * A. Memastikan primary shard dan replica-nya tidak dialokasikan pada node yang memiliki metadata attribute (misal: hardware rack/zone) yang sama.
   * B. Membagi data index secara merata antara OS Page Cache dan JVM Heap.
   * C. Memprioritaskan query hanya dijalankan pada CPU dengan arsitektur ARM.
   * D. Memaksa data node untuk menggunakan kartu jaringan tertentu.
9. Manakah kondisi yang **wajib** dipenuhi sebelum API `_shrink` dapat berhasil dijalankan pada index target?
   * A. Index harus dalam keadaan memiliki setidaknya 3 replica shard.
   * B. Salinan setiap shard dari index harus berada pada node yang sama secara lokal, dan index diset `index.blocks.write: true`.
   * C. Ukuran cluster harus memiliki node minimal 10 unit.
   * D. Translog harus dihapus secara manual.
10. Pada pola arsitektur Hot-Warm-Cold, decider apa yang dievaluasi Master Node saat memindahkan shard dari node bertipe `hot` ke `warm`?
    * A. `MaxRetryAllocationDecider`
    * B. `FilterAllocationDecider`
    * C. `SameShardAllocationDecider`
    * D. `ClusterRebalanceAllocationDecider`

#### C. Skenario Kasus Produksi (3 Pertanyaan Kasus)
11. **Skenario Kasus 1**:
    Sebuah aplikasi marketplace memiliki index `items_v1` dengan 20 shards. Traffic query rata-rata adalah 15.000 QPS. Tim infra mendapati CPU Coordinating Node konstan berada di level 98%, sementara Data Nodes hanya 25%. Metrik latency menunjukkan fase execute Lucene rata-rata hanya 2ms, namun response time diterima client adalah 450ms.
    *Pertanyaan*: Berdasarkan karakteristik arsitektur internal Elasticsearch, apa akar penyebab utama disparitas ini dan bagaimana solusi desain sharding/routing terbaik untuk menuntaskannya?
12. **Skenario Kasus 2**:
    Sebuah node data di Zone A mati mendadak karena kegagalan daya pada rak data center. Cluster diset dengan Shard Allocation Awareness (`attributes: zone`, Zone A & Zone B). Pada saat node tersebut mati, cluster state berubah menjadi `YELLOW`, namun replica shard di Zone B tidak langsung dipromosikan dan dialokasikan ke sisa node yang ada di Zone A. Mengapa perilaku ini terjadi secara desain, dan apa risiko terbesar jika engineer memaksa menonaktifkan awareness dalam kondisi darurat tersebut?
13. **Skenario Kasus 3**:
    Perusahaan multi-tenant B2B menggunakan skema routing `routing = company_id`. Salah satu customer korporasi melakukan migrasi ratusan juta dokumen historis dalam 24 jam. Tiba-tiba salah satu node mengalami `High Disk Watermark (90%)` dan Elasticsearch menandai index tersebut menjadi read-only karena menyentuh `Flood-Stage Disk Watermark (95%)`. Seluruh tenant lain di index tersebut ikut terdampak (tidak bisa insert). Jelaskan 3 tahapan pemulihan terukur (*immediate, intermediate, long-term architecture*) untuk mencegah insiden terulang!

---

### Kunci Jawaban & Pembahasan Evaluasi

#### Bagian A (Basic)
1. **C** - Murmur3 Hash adalah fungsi hashing non-kriptografis default yang digunakan Elasticsearch untuk pemetaan alokasi shard.
2. **B** - Untuk kebutuhan low-latency search, ukuran ideal adalah 10 GB - 25 GB per shard agar Lucene segment mudah dicache di OS memory.
3. **C** - Mapping setting `"_routing": { "required": true }` memaksa penolakan dokumen tanpa parameter routing.
4. **B** - Nilai maksimum yang diizinkan sebelum JVM beralih dari 32-bit compressed reference pointer ke 64-bit pointers murni (kehilangan optimasi memory footprint) berkisar di angka 31.5 GB.
5. **C** - `_shrink` API digunakan untuk memperkecil jumlah primary shards pada index non-aktif/read-only.

#### Bagian B (Intermediate)
6. **C** - `routing_partition_size` membagi ruang hash dokumen ke dalam subset yang ditentukan oleh ukuran partisi tersebut, sehingga query routing menyasar tepat 3 shard.
7. **B** - Shard Lucene membutuhkan struktur data memory in-heap untuk memegang index segment, terms dictionary, dan metadata cluster. Ribuan shard memicu memory exhaustion dan cluster state sync delay.
8. **A** - Awareness memastikan replika data disebar melintasi boundary domain fisik/virtual (rack, zona, cloud region).
9. **B** - Prasyarat mutlak Shrink API: Seluruh primary shard (atau salinannya) harus terkonsolidasi pada node yang sama, dan blok penulisan aktif (`index.blocks.write: true`).
10. **B** - Pemindahan shard antar-tier node memanfaatkan atribut kustom pada node via `FilterAllocationDecider` (misal: `index.routing.allocation.include._tier_preference`).

#### Bagian C (Kasus Produksi)
11. **Pembahasan Kasus 1**:
    *Akar Penyebab*: Terjadi overhead scatter-gather masif. Coordinating Node terbebani oleh network I/O serialization, thread pooling context-switch, dan merging priority queues dari 20 shards untuk 15.000 QPS ($15.000 \times 20 = 300.000$ shard query hops/detik).
    *Solusi*: Terapkan custom routing pada level user ID / shop ID. Ubah routing menjadi targeted query ($O(1)$) sehingga Coordinating Node cukup me-route langsung ke 1 shard tujuan tanpa melakukan local queue merge.
12. **Pembahasan Kasus 2**:
    *Penyebab*: Shard Awareness melarang penempatan replica di zona yang sama dengan primary-nya. Jika kapasitas node tersisa di Zone B tidak memiliki pasangan alokasi di Zone A, decider akan menahan pembuatan shard baru demi mematuhi fault tolerance boundary.
    *Risiko*: Menonaktifkan awareness saat zone mati akan memicu *data cascading imbalance*. Seluruh replica akan di-generate di Zone B. Ketika Zone A hidup kembali, cluster akan mengalami I/O storm masif akibat rebalancing ratusan gigabyte data antar-zona, berpotensi meruntuhkan performa throughput transaksi produksi.
13. **Pembahasan Kasus 3**:
    *Tahapan Terstruktur*:
    *   *Immediate (Mitigasi Darurat)*: Naikkan sementara disk flood-stage watermark via persistent cluster update setting (`cluster.routing.allocation.disk.watermark.flood_stage: "98%"`), lalu lepas read-only block pada index (`index.blocks.read_only_allow_delete: null`).
    *   *Intermediate (Balancing)*: Pindahkan shard yang tidak terdampak ke node lain secara manual menggunakan `_cluster/reroute` API, atau tambahkan disk storage instance pada node terkait.
    *   *Long-term (Solusi Arsitektural)*: Terapkan `routing_partition_size` untuk memecah data whale tenant ke multi-shard, dan pisahkan tenant enterprise raksasa ke dedicated index tersendiri (*index-per-tenant pattern* atau *tiering* khusus).

---

### 16. Summary
1. Algoritma alokasi shard mengandalkan hashing deterministik **Murmur3**. Pemahaman mendalam terkait formula hashing ini krusial saat merancang pemartisian data lintas cluster.
2. **Custom Routing** mengeliminasi pola komputasi mahal *Scatter-Gather*, mentransformasikan search latency dari agregasi multi-node menjadi eksekusi direct point-to-point $O(1)$.
3. Penggunaan custom routing tanpa mitigasi dapat memicu **Shard Hotspotting** (*data skew*). Mitigasi standar industri adalah mengombinasikan routing dengan `index.routing_partition_size`.
4. Kestabilan cluster enterprise ditentukan oleh disiplin alokasi: ukuran shard berada pada rentang **10–50 GB**, rasio shard tidak melewati **20 shards / 1 GB Heap**, serta topologi terlindungi via **Shard Allocation Awareness** multizona.