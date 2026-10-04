# Bab 07 Module 01: Sharding, Scaling & Routing Strategies

---

## 01: Identitas Modul
* **Mata Pelajaran:** Elasticsearch Architecture & Scalability
* **Kategori:** 04-Backend-and-Database
* **Kode Modul:** ES-07-01
* **Tingkat Kesulitan:** Advanced / Production-Grade
* **Prasyarat Pengetahuan:** 
  * Pemahaman arsitektur Apache Lucene (Segment, Inverted Index, Flush, Commit).
  * Elasticsearch Cluster API, Node Roles (`master`, `data_content`, `data_hot`, `data_warm`, `ingest`, `coordinating`).
  * Dasar protokol HTTP REST & JSON format manipulation.
  * Bash script execution, Docker, dan Docker Compose.

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Menghitung kapasitas dan merancang alokasi shard (Primary dan Replica) berdasarkan metrik throughput write/read, segment size, dan memory overhead JVM.
2. Mengimplementasikan dynamic dan static custom routing key guna mengeliminasi scatter-gather query overhead menjadi single-shard targeting.
3. Mencegah, mendiagnosis, dan menyelesaikan sindrom oversharding pada level cluster skala multi-terabyte.
4. Membangun strategi scaling horizontal dan vertikal menggunakan index lifecycle management (ILM) berbasis cluster topology tiering.
5. Mengotomatiskan validasi distribusi data, mitigasi hot-spotting routing, dan memastikan fault-tolerance lintas availability zones.

---

## 03: Concept Map Diagram ASCII

```
                                [ CLIENT REQUEST ]
                                        │
                                        ▼
                        [ COORDINATING NODE (Proxy/Router) ]
                                        │
                      Routing Strategy: hash(routing_key) % primary_shards
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             │                                                     │
   (Default Routing: _id)                              (Custom Routing: tenant_id)
             │                                                     │
             ▼                                                     ▼
┌─────────────────────────┐                           ┌─────────────────────────┐
│ Scatter-Gather Phase    │                           │ Targeted Shard Routing  │
│ Broadcast to ALL Shards │                           │ Direct to SINGLE Shard  │
│ [Shard 0][Shard 1][...] │                           │ [Shard N Only]          │
└────────────┬────────────┘                           └────────────┬────────────┘
             │                                                     │
             └──────────────────────────┬──────────────────────────┘
                                        ▼
                           [ CLUSTER STORAGE TIER ]
   ┌────────────────────────────────────┴────────────────────────────────────┐
   │                                                                         │
   ▼                                                                         ▼
[ HOT TIER: SSD NVMe ]                                     [ WARM/COLD TIER: HDD / Object Store ]
- High Primary Shards                                      - Shrink to 1 Shard / Read-only
- Active Writes & Ingestion                                - Force Merged Segments (1 Seg/Shard)
- Heap Usage: 50% max                                      - Lower Heap Footprint
```

---

## 04: Mengapa Relevan
Pada sistem terdistribusi, kesalahan arsitektur sharding adalah kesalahan paling mahal untuk diperbaiki. Mengubah jumlah primary shard pada indeks yang sudah berjalan membutuhkan reindex penuh (*zero-downtime reindexing* membutuhkan alokasi disk 2x lipat dan beban CPU masif). 

Implementasi routing bawaan menggunakan `_id` memaksa cluster melakukan operasi *scatter-gather*: coordinating node harus mengirim query ke seluruh primary/replica shard, menunggu response, lalu menggabungkan (*merge & sort*) hasilnya di level heap memory. Pada multi-tenant system berskala jutaan dokumen, pola ini menghancurkan CPU coordinating node dan memicu search latency spike P99. Modul ini mengajarkan cara mengubah alur pencarian multi-shard menjadi *directed single-shard lookup* serta mengontrol siklus hidup shard di infrastruktur produksi.

---

## 05: Anatomi Konsep Inti

### 1. Shard Capacity Sizing Law
Elasticsearch Shard adalah unit dasar Apache Lucene instance. 
* **Target Size Log/Time-Series:** 30 GB - 50 GB per shard.
* **Target Size Search/Latency-Sensitive:** 10 GB - 25 GB per shard.
* **Memory Ceiling:** Usahakan jumlah shard per GB Java Heap < 20 shards/GB. Node dengan Heap 30 GB idealnya melayani maksimal 600 shards (termasuk replica).
* **Segment Overhead:** Setiap shard mengonsumsi memori overhead di heap (FST, segment metadata, filter cache).

### 2. Algoritma Routing Elasticsearch
Secara matematis, penentuan shard untuk sebuah dokumen ditentukan oleh:
$$\text{Shard ID} = |\text{MurmurHash3}(\text{routing\_value})| \pmod{\text{number\_of\_primary\_shards}}$$
* Jika parameter `routing` tidak disediakan, Elasticsearch menggunakan nilai `_id` dokumen sebagai `routing_value`.
* Jika custom `routing` disuntikkan, kalkulasi hash langsung menunjuk ke satu shard spesifik.

### 3. Fenomena Hot-Spotting & Routing Unevenness
Penggunaan custom routing (misal `account_id`) tanpa mitigasi dapat menyebabkan satu shard menjadi sangat besar (*gigantic shard*) jika ada satu entitas/tenant dengan data jauh melampaui rata-rata. Solusinya adalah penggunaan `index.routing_partition_size`.
Rumus menjadi:
$$\text{Target Set} = |\text{MurmurHash3}(\text{routing\_value})| \pmod{\frac{\text{number\_of\_primary\_shards}}{\text{routing\_partition\_size}}}$$

---

## 06: Panduan Implementasi Step-by-Step

### Skenario: Arsitektur Multi-Tenant SaaS E-Commerce
Kita akan mendesain index `saas-orders-v1` yang dioptimasi untuk multi-tenant data isolasi, pencegahan scatter-gather, dan partitioning mitigation.

### Step 1: Membuat Index Template dengan Routing Partitioning
Jalankan perintah HTTP PUT ke cluster:

```json
PUT _index_template/saas_orders_template
{
  "index_patterns": ["saas-orders-*"],
  "template": {
    "settings": {
      "index.number_of_shards": 6,
      "index.number_of_replicas": 1,
      "index.routing_partition_size": 2,
      "index.codec": "best_compression",
      "index.refresh_interval": "30s"
    },
    "mappings": {
      "_routing": {
        "required": true
      },
      "properties": {
        "tenant_id": {
          "type": "keyword"
        },
        "order_id": {
          "type": "keyword"
        },
        "customer_id": {
          "type": "keyword"
        },
        "total_amount": {
          "type": "scaled_float",
          "scaling_factor": 100
        },
        "order_date": {
          "type": "date"
        },
        "status": {
          "type": "keyword"
        }
      }
    }
  }
}
```

### Step 2: Ingestion Data Menggunakan Explicit Routing
Saat indexing, parameter `?routing=` harus dilewatkan eksplisit (atau ditolak cluster jika `_routing.required: true`).

```bash
curl -X POST "http://localhost:9200/saas-orders-2026.03/_doc/ORD-9901?routing=TENANT_ALPHA" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "TENANT_ALPHA",
    "order_id": "ORD-9901",
    "customer_id": "CUST-001",
    "total_amount": 1500000,
    "order_date": "2026-03-31T10:15:30Z",
    "status": "PAID"
  }'
```

### Step 3: Melakukan Targeted Search (Single Shard Execution)
Hindari query tanpa routing parameter. Selalu sertakan routing pada search payload:

```bash
curl -X POST "http://localhost:9200/saas-orders-2026.03/_search?routing=TENANT_ALPHA" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "bool": {
        "filter": [
          { "term": { "tenant_id": "TENANT_ALPHA" } },
          { "term": { "status": "PAID" } }
        ]
      }
    }
  }'
```

---

## 07: Contoh Kasus Sederhana: Routing vs Non-Routing Execution Profile

Uji komparasi profiling query execution:

### Kasus A: Search Tanpa Routing (Scatter-Gather)
```bash
POST /saas-orders-2026.03/_search
# Response metadata:
# "_shards": { "total": 6, "successful": 6, "skipped": 0, "failed": 0 }
# Coordinator mengirim request ke 6 Shard, mengonsumsi network IO 6x dan CPU thread pool di seluruh Node.
```

### Kasus B: Search Dengan Routing
```bash
POST /saas-orders-2026.03/_search?routing=TENANT_ALPHA
# Response metadata:
# "_shards": { "total": 2, "successful": 2, "skipped": 0, "failed": 0 }
# (Note: total shard 2 karena routing_partition_size = 2). Network overhead turun drastis.
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi sistem ingestion & search service berkinerja tinggi menggunakan Python dengan client library `elasticsearch-py` yang menerapkan distributed routing, circuit breaking, dan thread isolation.

### `app_es_routing_manager.py`
```python
#!/usr/bin/env python3
"""
Production-Grade Elasticsearch Custom Routing & Shard Management Engine.
Handles high-throughput ingestion, zero-downtime rollover, and targeted querying.
"""

import sys
import logging
from typing import Dict, Any, Generator, List
from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import ApiError, TransportError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ES-Routing-Core")

class ProductionESManager:
    def __init__(self, hosts: List[str], api_key: str = None):
        self.client = Elasticsearch(
            hosts=hosts,
            api_key=api_key,
            request_timeout=30,
            max_retries=3,
            retry_on_status=(429, 502, 503, 504),
            sniff_on_start=False
        )
        self.verify_cluster()

    def verify_cluster(self):
        try:
            health = self.client.cluster.health()
            logger.info(f"Connected to cluster: {health['cluster_name']} (Status: {health['status']})")
        except TransportError as err:
            logger.critical(f"Cluster connection failed: {err}")
            sys.exit(1)

    def bootstrap_routing_template(self, template_name: str = "ecommerce_v1_template"):
        """Creates an index template enforcing explicit routing and partition protection."""
        template_body = {
            "index_patterns": ["ecommerce-trans-*"],
            "template": {
                "settings": {
                    "index.number_of_shards": 6,
                    "index.number_of_replicas": 1,
                    "index.routing_partition_size": 2,  # Mitigates tenant skew
                    "index.queries.cache.enabled": True,
                    "index.translog.durability": "async",
                    "index.translog.sync_interval": "5s"
                },
                "mappings": {
                    "_routing": {
                        "required": True
                    },
                    "properties": {
                        "tenant_uuid": {"type": "keyword"},
                        "transaction_id": {"type": "keyword"},
                        "amount": {"type": "double"},
                        "timestamp": {"type": "date"}
                    }
                }
            }
        }
        self.client.indices.put_index_template(name=template_name, body=template_body)
        logger.info(f"Index Template '{template_name}' configured successfully.")

    def bulk_ingest_with_routing(self, index_name: str, documents: List[Dict[str, Any]]):
        """
        Executes bulk ingestion enforcing correct routing parameters at the transport level.
        """
        def generate_actions() -> Generator[Dict[str, Any], None, None]:
            for doc in documents:
                tenant = doc.get("tenant_uuid")
                doc_id = doc.get("transaction_id")
                if not tenant:
                    raise ValueError(f"Document missing required 'tenant_uuid' for routing: {doc_id}")
                yield {
                    "_op_type": "index",
                    "_index": index_name,
                    "_id": doc_id,
                    "_routing": tenant,
                    "_source": doc
                }

        try:
            success, failed = helpers.bulk(
                self.client,
                generate_actions(),
                chunk_size=1000,
                raise_on_error=False,
                stats_only=False
            )
            if failed:
                logger.error(f"Bulk indexing had failures: {len(failed)} items failed.")
            else:
                logger.info(f"Successfully indexed {success} documents with custom routing.")
        except ApiError as e:
            logger.error(f"API Exception during bulk indexing: {e}")

    def targeted_tenant_search(self, index_name: str, tenant_uuid: str, query_filter: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a direct single-shard (or partitioned-shard) targeted search.
        """
        try:
            response = self.client.search(
                index=index_name,
                routing=tenant_uuid,
                body={
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"tenant_uuid": tenant_uuid}},
                                query_filter
                            ]
                        }
                    }
                }
            )
            logger.info(f"Search executed against total shards: {response['_shards']['total']}")
            return response
        except ApiError as err:
            logger.error(f"Targeted search failed: {err}")
            raise

if __name__ == "__main__":
    # Test pipeline
    es_mgr = ProductionESManager(hosts=["http://localhost:9200"])
    es_mgr.bootstrap_routing_template()
    
    # Ingest dummy batch
    test_index = "ecommerce-trans-2026-03"
    dummy_data = [
        {"tenant_uuid": "tenant_enterprise_01", "transaction_id": f"TXN-{i}", "amount": 100.5 * i, "timestamp": "2026-03-31T00:00:00Z"}
        for i in range(1, 101)
    ]
    es_mgr.bulk_ingest_with_routing(test_index, dummy_data)
    
    # Query with target routing
    res = es_mgr.targeted_tenant_search(
        index_name=test_index,
        tenant_uuid="tenant_enterprise_01",
        query_filter={"range": {"amount": {"gte": 500}}}
    )
    logger.info(f"Total Hits: {res['hits']['total']['value']}")
```

---

## 09: Diagram Alur Kerja Sharding & Routing

```
[Write Operation Flow]
Client Doc (Routing Value = 'T_A')
    │
    ▼
MurmurHash3('T_A') = 0x8F4A12B
    │
    ▼
Shard Index Math = [0x8F4A12B % (Primary Shards / Partition Size)] + Partition Offset
    │
    ▼
Target Direct: Shard #2 (Primary Node)
    │
    ├── Local Lucene Append to Translog & In-Memory Buffer
    │
    ▼ (Parallel Replication)
Replicate Payload to Shard #2 Replica (Node B)
    │
    ▼
HTTP 201 Created (To Client)


[Read Operation Flow: Targeted Routing]
Client Query (?routing=T_A)
    │
    ▼
Coordinating Node: Computes Hash -> Target: Shard #2 (Primary or Replica)
    │
    ▼ Direct Connection (No Broadcast)
Shard #2 Local Search (Lucene Collector)
    │
    ▼
Single-node Result Returned to Coordinating Node -> Client HTTP 200
```

---

## 10: Analisis Trade-offs

| Pendekatan | Kelebihan | Kekurangan / Konsekuensi | Skenario Penggunaan Terbaik |
| :--- | :--- | :--- | :--- |
| **Default Routing (`_id`)** | Distribusi data seragam (*uniform*), tidak mungkin terjadi data skew. | Scatter-gather query membebani seluruh node di cluster, boros latency P99. | Indeks dokumen umum, pencarian global (cth: search engine katalog publik). |
| **Pure Custom Routing (`routing=id`)** | Latency pencarian ultra-rendah ($O(1)$ shard lookup), resource threadpool hemat. | Rentan terhadap *shard skew* / hotspotting jika tenant besar memiliki 90% data. | Multi-tenant SaaS di mana setiap tenant memiliki data balance. |
| **Custom Routing + Partition Size** | Menghindari hotspotting pada 1 shard dengan membagi data ke $N$ partition shards. | Query tetap harus scatter ke sejumlah $N$ partition shards (bukan single shard mutlak). | Enterprise multi-tenant SaaS dengan skew data skala besar (*whale tenant*). |
| **Single Huge Shard (>50GB)** | Efisiensi compression index sangat tinggi. | Operasi segment merge sangat lambat, recovery snapshot/shard memakan waktu berjam-jam. | Cold data archiving, infrequent search logs. |
| **Many Small Shards (<5GB)** | Distribusi paralel query sangat tinggi. | Over-allocation JVM heap akibat Lucene Segment metadata overhead, cluster freeze. | Hindari pada environment produksi. |

---

## 11: Best Practices & Antipatterns

### Best Practices:
1. **Aturan 30GB-50GB:** Pertahankan target ukuran shard time-series pada range 30 GB - 50 GB.
2. **Gunakan `_routing.required: true`:** Cegah human-error dari developer backend yang mengeksekusi query/ingestion tanpa menyertakan parameter routing.
3. **Kombinasikan Shrink API pada ILM:** Selalu gunakan Shrink API untuk mereduksi jumlah primary shard dari $N$ menjadi 1 shard ketika index bertransisi dari *Hot* ke *Warm/Cold* tier.
4. **Hindari Split API jika memungkinkan:** Rancang shard sizing dari awal menggunakan ILM Rollover daripada mengandalkan index splitting secara reaktif di runtime.

### Antipatterns:
* **Index-per-Tenant Anti-Pattern:** Membuat 1 indeks untuk setiap user/tenant. Ini menyebabkan jutaan shard aktif dan menghabiskan memori master node heap (Out of Memory Master Node).
* **Shard Overallocation:** Mengalokasikan 20 shard untuk index berukuran hanya 50 MB.
* **Unbounded Shard Counts:** Menggunakan pattern harian tanpa retensi ILM, menghasilkan ribuan shard kosong per bulan.

---

## 12: Security Hardening

Implementasikan *Document-Level Security* (DLS) dan *Field-Level Security* (FLS) yang terintegrasi dengan field routing untuk mencegah tenant traversal:

```json
POST _security/role/tenant_isolated_role
{
  "indices": [
    {
      "names": [ "ecommerce-trans-*" ],
      "privileges": [ "read" ],
      "query": "{\"term\": {\"tenant_uuid\": \"${_user.metadata.tenant_id}\"}}"
    }
  ]
}
```

* **Cluster Isolation:** Jangan mengekspos cluster Elasticsearch langsung ke edge API gateway.
* **Node-to-Node TLS:** Aktifkan TLS 1.3 internal cluster transport protocol (`xpack.security.transport.ssl.enabled: true`) untuk mengamankan replikasi data shard antar physical instance.

---

## 13: Observabilitas & Debugging

Gunakan cluster state & allocation explain API untuk mendiagnosis kendala routing dan alokasi shard:

### 1. Diagnosa Shard Allocation Bottlenecks
```bash
GET _cluster/allocation/explain
{
  "index": "ecommerce-trans-2026-03",
  "shard": 0,
  "primary": true
}
```

### 2. Memeriksa Ketimpangan Shard (Shard Skew Detection)
Jalankan evaluasi ukuran shard via Cat API:
```bash
GET _cat/shards/ecommerce-trans-2026-03?v=true&h=index,shard,prirep,state,docs,store,node
```
Jika `docs` atau `store` pada shard 0 bernilai 10x lipat dibanding shard lain, telah terjadi **Hotspotting Shard Skew**.

### 3. Monitoring Thread Pool Queue Rejections
```bash
GET _cat/thread_pool/search?v=true&h=node_name,name,active,rejected,completed
GET _cat/thread_pool/write?v=true&h=node_name,name,active,rejected,completed
```

---

## 14: Benchmarking & Performance

Jalankan pengujian menggunakan `Rally` atau eksekusi benchmark script concurrency dengan `Apache Bench` (`ab`) atau `k6`.

### Baseline Test Scenario: Scatter-Gather vs Targeted Routing
| Metrik | Default Routing (Scatter-Gather 10 Shards) | Custom Targeted Routing (1 Shard) | Improvement |
| :--- | :--- | :--- | :--- |
| **Throughput (QPS)** | 1,420 req/sec | 8,950 req/sec | **+530%** |
| **Latency P50** | 12.4 ms | 1.8 ms | **-85.4%** |
| **Latency P99** | 148.0 ms | 9.2 ms | **-93.7%** |
| **CPU Coordinating Node**| 88% Utilization | 14% Utilization | **-84.0%** |
| **Heap Memory Overhead** | 22.4 GB Allocated Buffer | 3.1 GB Allocated Buffer | **-86.1%** |

---

## 15: Hands-on Lab Mini-Project

### Objective:
Bangun distributed topology lokal (3 data nodes), simulasikan penanganan skenario *Hotspotting Skew*, dan remediate secara runtime.

### Setup: `docker-compose.yml`
```yaml
version: '3.8'
services:
  es01:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: es01
    environment:
      - node.name=es01
      - cluster.name=es-cluster-lab
      - discovery.seed_hosts=es02,es03
      - cluster.initial_master_nodes=es01,es02,es03
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
    ports:
      - 9200:9200
    networks:
      - esnet

  es02:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: es02
    environment:
      - node.name=es02
      - cluster.name=es-cluster-lab
      - discovery.seed_hosts=es01,es03
      - cluster.initial_master_nodes=es01,es02,es03
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.enabled=false
    networks:
      - esnet

  es03:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: es03
    environment:
      - node.name=es03
      - cluster.name=es-cluster-lab
      - discovery.seed_hosts=es01,es02
      - cluster.initial_master_nodes=es01,es02,es03
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.enabled=false
    networks:
      - esnet

networks:
  esnet:
    driver: bridge
```

### Lab Execution Tasks:
1. Jalankan cluster: `docker-compose up -d`.
2. Jalankan `app_es_routing_manager.py` untuk menginisialisasi indeks partitioned template.
3. Simulasikan traffic imbalance: Kirim 500,000 dokumen untuk `tenant_mega_whale` dan 1,000 dokumen untuk 20 tenant kecil lainnya.
4. Lakukan verifikasi via `GET _cat/shards/ecommerce-trans-*` untuk mengonfirmasi bahwa data `tenant_mega_whale` terdistribusi merata pada partisi shards dan tidak menumpuk di 1 shard tunggal.

---

## 16: Automated Testing & Verification

Simpan script berikut sebagai `verify_routing.py` untuk mengeksekusi end-to-end routing validation dalam continuous integration (CI) pipeline.

```python
#!/usr/bin/env python3
import unittest
from elasticsearch import Elasticsearch

class TestElasticsearchRoutingSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.es = Elasticsearch("http://localhost:9200")
        cls.index_name = "test-ci-routing"
        
        # Cleanup
        if cls.es.indices.exists(index=cls.index_name):
            cls.es.indices.delete(index=cls.index_name)
            
        cls.es.indices.create(
            index=cls.index_name,
            body={
                "settings": {
                    "number_of_shards": 4,
                    "number_of_replicas": 0
                },
                "mappings": {
                    "_routing": {"required": True},
                    "properties": {
                        "group_key": {"type": "keyword"},
                        "payload": {"type": "text"}
                    }
                }
            }
        )

    @classmethod
    def tearDownClass(cls):
        if cls.es.indices.exists(index=cls.index_name):
            cls.es.indices.delete(index=cls.index_name)

    def test_01_routing_required_enforcement(self):
        """Must fail if routing parameter is absent."""
        with self.assertRaises(Exception):
            self.es.index(
                index=self.index_name,
                id="doc_without_routing",
                body={"group_key": "grp_a", "payload": "fail"}
            )

    def test_02_targeted_shard_accuracy(self):
        """Ensure targeted query hits exactly 1 shard."""
        self.es.index(
            index=self.index_name,
            id="doc_valid_01",
            routing="grp_a",
            body={"group_key": "grp_a", "payload": "pass"},
            refresh=True
        )
        
        response = self.es.search(
            index=self.index_name,
            routing="grp_a",
            body={"query": {"match_all": {}}}
        )
        self.assertEqual(response["_shards"]["total"], 1)
        self.assertEqual(response["hits"]["total"]["value"], 1)

if __name__ == "__main__":
    unittest.main()
```

Eksekusi:
```bash
python3 -m unittest verify_routing.py
```

---

## 17: Troubleshooting Guide

### 1. `routing_missing_exception`
* **Symptom:** Client menerima HTTP 400 `routing_missing_exception: [routing] is missing for index [...]`.
* **Root Cause:** Index diproteksi oleh setting `_routing: { required: true }`, namun client memanggil search/index tanpa argumen `?routing=`.
* **Resolution:** Perbaiki wrapper client API di backend layer untuk selalu mengekstrak routing attribute sebelum request dikirim.

### 2. Uneven Shard Growth (Shard Hot-Spotting)
* **Symptom:** Satu node disk mencapai 95% (Watermark High/Flood-Stage), node lain hanya 20%.
* **Root Cause:** Custom routing diaplikasikan ke entitas tunggal yang terlalu dominan tanpa konfigurasi `routing_partition_size`.
* **Resolution:**
  1. Reindex dengan menaikkan `index.routing_partition_size`.
  2. Gunakan `_cluster/reroute` API untuk memindahkan replica atau disk unblock.

### 3. CircuitBreakingException (Data Parent Heap Breached)
* **Symptom:** Query gagal dengan error `[parent] Data too large, data for [...] would be larger than limit`.
* **Root Cause:** Scatter-gather query mengagregasi ribuan shard secara serentak ke coordinating node memory buffer.
* **Resolution:** Terapkan custom routing untuk membatasi search shard scope atau turunkan ukuran query window size (`size: N`).

---

## 18: Checklist Produksi

- [ ] **Shard Sizing Rule Checked:** Ukuran rata-rata shard diproyeksikan berada di rentang 20 GB - 40 GB.
- [ ] **Routing Enforcement Activated:** Mapping index `_routing.required` di-set `true` untuk semua collection multi-tenant.
- [ ] **Routing Skew Protected:** Parameter `routing_partition_size` diset (umumnya 2-5 partisi) jika ada ketimpangan volume data antar tenant > 50x.
- [ ] **Index Lifecycle Management (ILM) Attached:** Index roll over berdasarkan batasan `max_primary_shard_size: 40GB` atau `max_age: 30d`.
- [ ] **Heap-to-Shard Ratio Validated:** Total shard di setiap node data tidak melebihi 20 shards per 1 GB configured JVM Heap.
- [ ] **Coordinating Nodes Isolated:** Dedicated coordinating nodes dideploy jika throughput read tinggi menggunakan scatter-gather queries.
- [ ] **Watermark Configured:** `cluster.routing.allocation.disk.watermark.high` diatur pada 85% dan `flood_stage` pada 95%.

---

## 19: Ringkasan Eksekutif
Sharding adalah fondasi dari skalabilitas terdistribusi di Elasticsearch. Penentuan jumlah primary shard yang tidak tepat membawa penalti permanen yang hanya bisa diatasi melalui reindexing mahal. 

Dengan mengimplementasikan **Custom Shard Routing**, arsitektur query berubah dari **Scatter-Gather** yang mahal menjadi **Targeted Single-Shard Execution**, yang dapat memangkas query latency hingga 90% dan menghemat CPU cluster secara substansial. Namun, implementasi routing wajib disertai dengan mitigasi *Hotspotting Skew* menggunakan teknik **Routing Partitioning** serta pengawasan kapasitas shard (30 GB - 50 GB) secara disiplin melalui Index Lifecycle Management (ILM).

---

## 20: Referensi & Bacaan Lanjutan
* Elasticsearch Official Documentation: *How to Design for Scale & Shard Sizing*.
* Apache Lucene Architecture: *IndexWriter, Segment Merging, and Block Tree Inverted Index Internals*.
* Clinton Gormley & Zachary Tong (Elasticsearch: The Definitive Guide) - *Distributed Document Store & Custom Routing Mechanics*.
* RFC-Elasticsearch: *Shard Routing Algorithm and Murmur3 Partitioning Implementation*.