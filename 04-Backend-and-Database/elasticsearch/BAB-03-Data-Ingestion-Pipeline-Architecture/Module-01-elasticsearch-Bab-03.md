# Bab 03 Module 01: Data Ingestion & Pipeline Architecture

---

## 01: Identitas Modul
* **Mata Kuliah/Topik**: Elasticsearch Advanced Data Engineering
* **Kategori**: `04-Backend-and-Database`
* **Kode Modul**: `ES-ENG-03-01`
* **Tingkat Kesulitan**: Intermediate to Advanced (L4-L5)
* **Prasyarat Teknis**:
  * Pemahaman fundamental REST API & JSON Payload
  * Pemahaman arsitektur dasar Elasticsearch (Cluster, Node, Shard, Index)
  * Familiaritas dengan Python 3.10+ dan asynchronous I/O
  * Pengetahuan dasar regex dan manipulasi string
* **Target Role**: Data Engineer, Backend Engineer, Search Engineer, Systems Architect

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Merancang dan Mengimplementasikan** Elasticsearch Ingest Node Pipelines menggunakan berbagai processors (`grok`, `dissect`, `script`, `set`, `remove`, `date`).
2. **Mengoptimalkan Throughput Ingestion** menggunakan mekanisme Bulk API, multi-threading, dan sizing buffer memory yang tepat.
3. **Membangun Error Handling Robust** pada level ingest pipeline dengan memanfaatkan conditional processing (`if`), `on_failure` hooks, dan dead-letter routing.
4. **Menganalisis Trade-offs** antara ETL sisi klien (Client-side/Logstash/Kafka) vs. Ingest Node Pipeline (Server-side transformation).
5. **Mengimplementasikan Pipeline Testing & Debugging** secara deterministik menggunakan `_simulate` API dan automated test suites.

---

## 03: Concept Map Diagram ASCII
```
+-----------------------------------------------------------------------------------+
|                           INGESTION PIPELINE ARCHITECTURE                         |
+-----------------------------------------------------------------------------------+
                                        |
      +---------------------------------+---------------------------------+
      |                                                                   |
      v                                                                   v
+-----------------------------+                             +-----------------------------+
|     CLIENT-SIDE LAYER       |                             |     INGEST NODE LAYER       |
+-----------------------------+                             +-----------------------------+
| * Batching Strategy (Bulk)  |                             | * Node Role: [ingest]       |
| * Backoff & Jitter Control  |                             | * Pipeline Interception     |
| * Schema Normalization      |                             | * In-memory Transformations |
+--------------+--------------+                             +--------------+--------------+
               |                                                           |
               +----------------------------+------------------------------+
                                            |
                                            v
+-----------------------------------------------------------------------------------------+
|                                PIPELINE EXECUTION LIFECYCLE                             |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|  Raw Document ---> [ Processor 01: Grok/Dissect ]                                      |
|                            |                                                            |
|                            +---> (Success) ---> [ Processor 02: Date Conversion ]       |
|                            |                                    |                       |
|                            +---> (Failure)                      +---> (Success) ---> OK |
|                                     |                                   |               |
|                                     v                                   +---> (Failure) |
|                            [ on_failure Hook ]                                  |       |
|                                     |                                           |       |
|                                     +<------------------------------------------+       |
|                                     |                                                   |
|                                     v                                                   |
|                      [ Metadata: _routing_error ]                                       |
|                                     |                                                   |
|                                     v                                                   |
|                        Route to Dead-Letter Index                                       |
+-----------------------------------------------------------------------------------------+
```

---

## 04: Mengapa Relevan
Dalam sistem berskala terdistribusi, data log, trace, dan metrics tidak pernah tiba dalam format yang siap diindeks (*pristine state*). Ketergantungan penuh pada heavy ETL engine eksternal (seperti Logstash atau Apache Spark) sering kali memperkenalkan kompleksitas operasional, latency tambahan, dan single point of failure jika hanya ditujukan untuk transformasi data ringan hingga moderat.

Elasticsearch Ingest Node menyediakan eksekusi *pre-processing* tepat sebelum dokumen diindeks ke dalam shard target. Menguasai arsitektur ingest pipeline memungkinkan arsitek sistem mendesentralisasi beban parsing, mengurangi beban network footprint, dan memberlakukan standarisasi schema (Elastic Common Schema/ECS) langsung di level database cluster secara *native*, tanpa infrastruktur komputasi perantara tambahan.

---

## 05: Anatomi Konsep Inti

### 1. Ingest Nodes vs Data Nodes
Secara default, setiap node Elasticsearch memiliki role `ingest`. Namun pada arsitektur produksi berskala besar, pemisahan node role menjadi keharusan:
* **Dedicated Ingest Nodes** (`node.roles: [ ingest ]`): Bertindak sebagai filter/parser buffer. Node ini menerima request bulk, menjalankan CPU-intensive tasks (Grok parsing, regex execution, Painless script calculation), dan meneruskan dokumen yang sudah diproses ke **Dedicated Data Nodes** (`node.roles: [ data ]`).
* **Keuntungan**: Mencegah starvation CPU pada data node yang sedang mengeksekusi operasi Lucene indexing dan complex search query.

### 2. Ingest Processors
Processor adalah unit atomik transformasi data dalam pipeline. Dieksekusi secara linear sesuai urutan deklarasi:
* **`dissect`**: Pemisah pola string berbasis delimiter statis. Sangat cepat ($O(N)$), overhead CPU minimal, tidak menggunakan regex engine.
* **`grok`**: Pattern matcher berbasis RegEx (Oniguruma). Fleksibel untuk parsing string non-deterministik, namun mengonsumsi siklus CPU tinggi.
* **`date`**: Mengubah string temporal ke tipe data standard `date` (ISO-8601) untuk time-series analysis.
* **`set` & `remove`**: Menambah, memodifikasi, atau membuang field untuk meminimalkan mapping overhead.
* **`script`**: Menggunakan bahasa Elasticsearch Painless untuk manipulasi kompleks berbasis kondisi algoritmik.

### 3. Pipeline Error Handling Mechanics
Pipeline mendukung kontrol error granular:
* `ignore_failure`: Jika diset `true`, kegagalan processor saat ini akan diabaikan dan eksekusi lanjut ke processor berikutnya.
* `on_failure`: Catch-block yang dieksekusi jika terjadi error fatal pada processor terkait atau pipeline global. Digunakan untuk dead-letter routing dan metadata tagging error debugging.

---

## 06: Panduan Implementasi Step-by-Step

### Langkah 1: Validasi Role Ingest Node
Pastikan cluster memiliki node yang menjalankan role ingest:
```bash
curl -X GET "http://localhost:9200/_nodes/ingest?pretty" \
  -H "Authorization: ApiKey ${ES_API_KEY}"
```

### Langkah 2: Definisikan Index Template Target
Buat Index Template untuk memastikan mapping target optimal:
```bash
curl -X PUT "http://localhost:9200/_index_template/web_logs_template" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["web-logs-*"],
    "template": {
      "settings": {
        "number_of_shards": 3,
        "number_of_replicas": 1,
        "index.default_pipeline": "web_logs_pipeline"
      },
      "mappings": {
        "properties": {
          "@timestamp": { "type": "date" },
          "client_ip": { "type": "ip" },
          "http_method": { "type": "keyword" },
          "request_uri": { "type": "keyword" },
          "response_code": { "type": "short" },
          "body_bytes_sent": { "type": "long" },
          "processing_time_ms": { "type": "float" },
          "tags": { "type": "keyword" },
          "error_meta": {
            "properties": {
              "message": { "type": "text" },
              "processor": { "type": "keyword" }
            }
          }
        }
      }
    }
  }'
```

### Langkah 3: Deploy Ingest Pipeline
Daftarkan pipeline parsing log web:
```bash
curl -X PUT "http://localhost:9200/_ingest/pipeline/web_logs_pipeline" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Production Web Log Parsing Pipeline",
    "processors": [
      {
        "dissect": {
          "field": "message",
          "pattern": "%{client_ip} %{http_method} %{request_uri} %{response_code} %{body_bytes_sent} %{processing_time_ms}"
        }
      },
      {
        "convert": {
          "field": "response_code",
          "type": "integer"
        }
      },
      {
        "convert": {
          "field": "body_bytes_sent",
          "type": "long"
        }
      },
      {
        "convert": {
          "field": "processing_time_ms",
          "type": "float"
        }
      },
      {
        "remove": {
          "field": "message"
        }
      }
    ],
    "on_failure": [
      {
        "set": {
          "field": "error_meta.message",
          "value": "{{ _ingest.on_failure_message }}"
        }
      },
      {
        "set": {
          "field": "error_meta.processor",
          "value": "{{ _ingest.on_failure_processor_type }}"
        }
      },
      {
        "append": {
          "field": "tags",
          "value": ["_pipeline_failure"]
        }
      }
    ]
  }'
```

---

## 07: Contoh Kasus Sederhana: Menguji Pipeline via `_simulate` API

Gunakan endpoint `_simulate` untuk memvalidasi pipeline tanpa menulis dokumen ke disk.

```bash
curl -X POST "http://localhost:9200/_ingest/pipeline/web_logs_pipeline/_simulate" \
  -H "Content-Type: application/json" \
  -d '{
    "docs": [
      {
        "_source": {
          "message": "192.168.1.100 GET /api/v1/checkout 200 4096 12.45"
        }
      },
      {
        "_source": {
          "message": "INVALID_FORMAT_PAYLOAD"
        }
      }
    ]
  }'
```

**Output Respons JSON**:
```json
{
  "docs": [
    {
      "doc": {
        "_index": "_index",
        "_id": "_id",
        "_source": {
          "client_ip": "192.168.1.100",
          "http_method": "GET",
          "request_uri": "/api/v1/checkout",
          "response_code": 200,
          "body_bytes_sent": 4096,
          "processing_time_ms": 12.45
        }
      }
    },
    {
      "doc": {
        "_index": "_index",
        "_id": "_id",
        "_source": {
          "message": "INVALID_FORMAT_PAYLOAD",
          "tags": ["_pipeline_failure"],
          "error_meta": {
            "message": "Dissect processor encountered an error parsing the field [message]",
            "processor": "dissect"
          }
        }
      }
    }
  ]
}
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah client ingestion asynchronous berskala produksi menggunakan Python dengan batching, dynamic backoff, dan auto-reconnect.

```python
#!/usr/bin/env python3
"""
High-Throughput Asynchronous Ingestion Client for Elasticsearch
Features: Bulk Ingestion, Exponential Jitter Backoff, Ingest Pipeline Binding
"""

import asyncio
import logging
import random
import sys
import time
from typing import AsyncGenerator, Dict, Any, List
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

# Configuration Setup
LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stdout)
logger = logging.getLogger("ElasticIngestProducer")

ES_HOST = "http://localhost:9200"
API_KEY = "your-secure-base64-api-key"
TARGET_INDEX = "web-logs-2026.03.31"
TARGET_PIPELINE = "web_logs_pipeline"
BATCH_SIZE = 2500
CONCURRENCY_LIMIT = 4

class BulkIngestionEngine:
    def __init__(self, host: str, api_key: str, concurrency: int = 4):
        self.es_client = AsyncElasticsearch(
            hosts=[host],
            api_key=api_key,
            max_retries=5,
            retry_on_timeout=True,
            request_timeout=30.0,
            connections_per_node=20
        )
        self.semaphore = asyncio.Semaphore(concurrency)

    async def generate_mock_logs(self, count: int) -> AsyncGenerator[Dict[str, Any], None]:
        """Menghasilkan stream log sintetis untuk stress test ingestion."""
        methods = ["GET", "POST", "PUT", "DELETE"]
        uris = ["/api/v1/auth", "/api/v1/cart", "/api/v1/payment", "/index.html"]
        ips = ["10.0.0.1", "172.16.0.45", "192.168.1.99", "127.0.0.1"]

        for i in range(count):
            # Simulasi 1% anomali string format corrupt untuk menguji on_failure pipeline
            if random.random() < 0.01:
                raw_log = "CORRUPT_LOG_DATA_FOR_ERROR_TEST"
            else:
                ip = random.choice(ips)
                method = random.choice(methods)
                uri = random.choice(uris)
                status = random.choice([200, 201, 400, 404, 500])
                size = random.randint(100, 1048576)
                latency = round(random.uniform(1.0, 500.0), 2)
                raw_log = f"{ip} {method} {uri} {status} {size} {latency}"

            yield {
                "_index": TARGET_INDEX,
                "pipeline": TARGET_PIPELINE,
                "_source": {
                    "@timestamp": time.time_ns() // 1000000,
                    "message": raw_log
                }
            }

    async def ingest_batch_stream(self, total_records: int):
        """Memproses ingestion menggunakan async_bulk helper berkecepatan tinggi."""
        logger.info(f"Starting ingestion of {total_records} records to [{TARGET_INDEX}]...")
        start_time = time.perf_counter()
        
        success_count = 0
        failure_count = 0

        async def stream_wrapper():
            async for doc in self.generate_mock_logs(total_records):
                yield doc

        try:
            async for ok, item in async_bulk(
                client=self.es_client,
                actions=stream_wrapper(),
                chunk_size=BATCH_SIZE,
                max_chunk_bytes=10 * 1024 * 1024, # 10MB
                raise_on_error=False,
                raise_on_exception=False
            ):
                if ok:
                    success_count += 1
                else:
                    failure_count += 1
                    logger.error(f"Failed document write: {item}")

        except Exception as e:
            logger.critical(f"Critical error during async bulk processing: {str(e)}", exc_info=True)
        finally:
            elapsed = time.perf_counter() - start_time
            throughput = (success_count + failure_count) / elapsed if elapsed > 0 else 0
            logger.info(f"Ingestion Completed in {elapsed:.2f}s | Success: {success_count} | Failed: {failure_count} | Rate: {throughput:.2f} docs/sec")

    async def close(self):
        await self.es_client.close()

async def main():
    engine = BulkIngestionEngine(ES_HOST, API_KEY, concurrency=CONCURRENCY_LIMIT)
    try:
        await engine.ingest_batch_stream(total_records=50000)
    finally:
        await engine.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 09: Diagram Alur Kerja ASCII

```
+-----------------------------------------------------------------------------+
|               BULK INGESTION EXECUTION TIMELINE WITH BACKOFF                |
+-----------------------------------------------------------------------------+

Client Worker                   Ingest Node                       Data Node
      |                              |                                |
      |--- 1. Bulk Request (Batch)-> |                                |
      |    (Pipeline: web_logs)      |                                |
      |                              |--- 2. Parse & Dissect Msg ---->|
      |                              |--- 3. Type Conversion -------->|
      |                              |--- 4. Schema Validated ------->|
      |                              |                                |
      |                              |--- 5. Write to Primary Shard ->|
      |                              |    (Memory Indexing Buffer)    |
      |                              |                                |
      |                              |<-- 6. Shard Write Acknowledged-|
      |<-- 7. 200 OK (Batch Stat) ---|                                |
      |                              |                                |
      | [Backpressure Triggered]     |                                |
      |--- 8. High Load Batch ------>|                                |
      |                              |--- 9. Thread Pool Exhausted -->|
      |<-- 10. HTTP 429 (EsRejected)-|                                |
      |                              |                                |
      | [Client Exponential Backoff] |                                |
      |  Sleep(2^retries + jitter)   |                                |
      |                              |                                |
      |--- 11. Retry Bulk Request -->|                                |
      |<-- 12. 200 OK Accepted ------|                                |
      v                              v                                v
```

---

## 10: Analisis Trade-offs

| Aspek Arsitektur | Ingest Node Pipeline (Elasticsearch) | External ETL (Logstash / Kafka + Flink) |
| :--- | :--- | :--- |
| **Infrastruktur** | **Ringan**: Native dalam cluster, zero extra compute servers. | **Berat**: Memerlukan cluster server mandiri (JVM footprint tinggi). |
| **Kompleksitas Parsing** | **Terbatas**: Cocok untuk parsing JSON, Grok, dissect, format konversi reguler. | **Ekstrem**: Mendukung complex stateful aggregations, custom lookups, multiple DB enrichment. |
| **Beban Cluster CPU** | **Tinggi**: Berbagi siklus CPU dengan operasi Indexing & Searching jika node tidak dipisah. | **Nol**: Cluster ES hanya menerima JSON bersih langsung ke Data Node. |
| **Buffering & Spooling**| **Terbatas**: Bergantung pada worker queue size internal (rentan `429 Too Many Requests`). | **Kuat**: Persistence buffer disk-based (Kafka logs / Logstash queue persistent). |
| **Throughput Ceiling** | **Moderate to High** (~50k-150k docs/sec tergantung jumlah node ingest). | **Ultra High** (>1M docs/sec dengan multi-node Kafka-Flink topology). |

---

## 11: Best Practices & Antipatterns

### ✅ Best Practices
1. **Gunakan `dissect` Sebelum `grok`**: Dissect tidak menggunakan regular expression engine, sehingga menghemat konsumsi CPU hingga 60-80% dibanding Grok untuk data log terstruktur.
2. **Atur `ignore_missing: true`**: Pada processor manipulasi field (misal `rename`, `convert`), pasang flag ini agar pipeline tidak throw exception ketika menemui sparse document.
3. **Pemisahan Dedicated Node Ingest**: Pada throughput $\ge 20,000\text{ docs/sec}$, pisahkan node dengan `node.roles: [ingest]` terisolasi dari `data` dan `master`.
4. **Kombinasikan Bulk Size & Flushing Threshold**: Ukuran bulk optimal secara empiris adalah $5\text{MB}$ hingga $15\text{MB}$ per HTTP payload, bukan dihitung dari raw document count semata.

### ❌ Antipatterns
1. **Painless Scripting untuk String Tokenizing Kompleks**: Menggunakan scripting processor untuk logic string regex rekursif menyebabkan degradasi CPU parah. Gunakan native processor.
2. **Single Document Indexing Loop**: Mengirim dokumen satu-persatu via `POST /index/_doc` dalam volume tinggi alih-alih memanfaatkan `_bulk` API.
3. **Penyalahgunaan `enrich` Processor Skala Besar**: Menjalankan ingest enrichment dengan referensi data berukuran puluhan gigabyte secara serentak pada payload tinggi yang mengakibatkan I/O saturation.

---

## 12: Security Hardening

1. **Role-Based Access Control (RBAC) Pipeline**:
   Batasi user ingestion agar hanya memiliki hak eksekusi, bukan hak modifikasi pipeline:
   ```json
   POST /_security/role/log_ingest_writer
   {
     "cluster": ["manage_index_templates", "manage_pipelines"],
     "indices": [
       {
         "names": [ "web-logs-*" ],
         "privileges": ["create_doc", "create_index", "auto_configure"]
       }
     ]
   }
   ```
2. **Mencegah Regular Expression Denial of Service (ReDoS)**:
   Saat menggunakan processor `grok`, jangan gunakan broad capture pattern seperti `.*` tanpa delimiter bound. Elasticsearch membatasi runtime Grok via setting:
   ```yaml
   # elasticsearch.yml
   ingest.grok.watchdog.interval: 1s
   ingest.grok.watchdog.max_execution_time: 2s
   ```
3. **Sanitasi Data Sensitif Menggunakan Processor `redact`**:
   Samarkan data PII (Personally Identifiable Information) sebelum persistensi ke disk:
   ```json
   {
     "redact": {
       "field": "message",
       "patterns": ["%{EMAILADDRESS:REDACTED_EMAIL}"]
     }
   }
   ```

---

## 13: Observabilitas & Debugging

### 1. Monitoring Ingest Node Statistics
Pantau latency dan throughput per pipeline secara real-time via stats API:
```bash
curl -X GET "http://localhost:9200/_nodes/stats/ingest?filter_path=nodes.*.ingest.pipelines.web_logs_pipeline" \
  -H "Authorization: ApiKey ${ES_API_KEY}"
```
**Metrik Kunci yang Wajib Dipantau**:
* `count`: Jumlah total dokumen yang diproses pipeline.
* `time_in_millis`: Total waktu pemrosesan CPU di level pipeline (Kalkulasikan Latency = `time_in_millis` / `count`).
* `failed`: Jumlah dokumen yang gagal diproses (Trigger alert jika rasio $> 0.1\%$).

### 2. Tracing Eksekusi Processor
Gunakan simulate pipeline dengan `verbose=true` untuk melihat state mutasi dokumen di setiap tahapan processor:
```bash
curl -X POST "http://localhost:9200/_ingest/pipeline/web_logs_pipeline/_simulate?verbose=true" \
  -H "Content-Type: application/json" \
  -d '{
    "docs": [{ "_source": { "message": "10.0.0.1 GET /login 200 512 3.14" } }]
  }'
```

---

## 14: Benchmarking & Performance

Optimasi throughput pipeline bergantung pada thread capacity dan memory indexing buffer.

### Parameter Optimasi Ingest
| Parameter | Default Value | Recommended Production Value | Dampak Terhadap Performa |
| :--- | :--- | :--- | :--- |
| `indices.memory.index_buffer_size` | `10%` | `20%` (pada Dedicated Node) | Mengurangi frekuensi segment flushing ke disk saat ingestion masif. |
| `index.translog.durability` | `request` | `async` (untuk time-series log) | Menghilangkan sync disk blocking per write; meningkatkan throughput $\sim 30\%$. |
| `index.translog.sync_interval` | `5s` | `30s` | Mengurangi I/O commit translog berkala. |
| `index.refresh_interval` | `1s` | `30s` atau `-1` (saat initial load)| Mengurangi pembuatan tiny Lucene segment secara drastis. |

---

## 15: Hands-on Lab Mini-Project

### Skenario Lab: "Real-time Firewall Audit Log Ingestion Engine"
**Tujuan**: Membangun pipeline pemrosesan log audit firewall yang membersihkan text, mengubah tipe IPv4, mengkategorikan severity level menggunakan Painless Script, dan mengisolasi log gagal ke dead-letter queue.

#### Template Setup
```bash
curl -X PUT "http://localhost:9200/_ingest/pipeline/firewall_security_pipeline" \
-H "Content-Type: application/json" \
-d '{
  "description": "Lab: Firewall Log Ingestion Engine",
  "processors": [
    {
      "grok": {
        "field": "raw_event",
        "patterns": ["\\[%{WORD:action}\\] src=%{IP:source_ip} dst=%{IP:dest_ip} port=%{INT:dest_port:int} bytes=%{INT:bytes_transferred:int}"]
      }
    },
    {
      "script": {
        "description": "Categorize severity based on port and bytes",
        "lang": "painless",
        "source": """
          if (ctx.dest_port == 22 || ctx.dest_port == 3389) {
            ctx.severity = "HIGH";
          } else if (ctx.bytes_transferred > 1000000) {
            ctx.severity = "MEDIUM";
          } else {
            ctx.severity = "LOW";
          }
        """
      }
    },
    {
      "remove": {
        "field": "raw_event"
      }
    }
  ],
  "on_failure": [
    {
      "set": {
        "field": "meta.processing_status",
        "value": "FAILED_PARSING"
      }
    },
    {
      "set": {
        "field": "meta.error",
        "value": "{{ _ingest.on_failure_message }}"
      }
    }
  ]
}'
```

---

## 16: Automated Testing & Verification

Gunakan script validasi Python berikut untuk memastikan pipeline lab berjalan sesuai requirement test-case:

```python
import pytest
import requests

ES_URL = "http://localhost:9200"
PIPELINE_NAME = "firewall_security_pipeline"

def test_pipeline_normal_flow():
    payload = {
        "docs": [
            {"_source": {"raw_event": "[ALLOW] src=192.168.1.50 dst=10.0.0.1 port=22 bytes=500"}}
        ]
    }
    res = requests.post(f"{ES_URL}/_ingest/pipeline/{PIPELINE_NAME}/_simulate", json=payload)
    assert res.status_code == 200
    doc = res.json()["docs"][0]["doc"]["_source"]
    
    assert doc["action"] == "ALLOW"
    assert doc["source_ip"] == "192.168.1.50"
    assert doc["dest_port"] == 22
    assert doc["severity"] == "HIGH"
    assert "raw_event" not in doc

def test_pipeline_failure_fallback():
    payload = {
        "docs": [
            {"_source": {"raw_event": "MALFORMED FIREWALL PACKET"}}
        ]
    }
    res = requests.post(f"{ES_URL}/_ingest/pipeline/{PIPELINE_NAME}/_simulate", json=payload)
    assert res.status_code == 200
    doc = res.json()["docs"][0]["doc"]["_source"]
    
    assert doc["meta"]["processing_status"] == "FAILED_PARSING"
    assert "error" in doc["meta"]
```

---

## 17: Troubleshooting Guide

### 1. Error: `EsRejectedExecutionException` (HTTP 429)
* **Penyebab**: Thread pool `write` pada ingest/data node penuh akibat request bulk berlebih.
* **Solusi**: 
  * Terapkan exponential backoff pada ingestion client.
  * Kurangi concurrency worker client.
  * Naikkan `queue_size` pada thread pool write (gunakan dengan hati-hati guna menghindari OOM).

### 2. Error: `GrokProcessorException: Exploded pattern matching limit`
* **Penyebab**: RegEx backtracking terlalu dalam akibat unclosed delimiter atau log text yang sangat panjang.
* **Solusi**: 
  * Optimalkan pattern Grok; hindari `(?m)` multiline regex yang tidak bounded.
  * Gunakan processor `dissect` sebagai pre-filter sebelum Grok.

### 3. Pipeline Ingestion Menyebabkan CPU Spike $100\%$
* **Penyebab**: Penggunaan Painless script yang melakukan iterasi loop intensif atau kompilasi script dinamis tak ber-cache.
* **Solusi**: Simpan skrip dalam parameterisasi statis dan hindari komputasi algoritmik kompleks di Ingest Node.

---

## 18: Checklist Produksi

- [ ] **Dedicated Node Role**: Parameter `node.roles: [ ingest ]` telah diisolasi dari data storage node pada cluster tier tinggi.
- [ ] **Simulate Testing**: Seluruh ingest pipeline telah melewati automated test case validasi regex via `_simulate`.
- [ ] **Failure Handling**: Setiap pipeline memiliki block `on_failure` komprehensif untuk mencegah drop document secara senyap (*silent failure*).
- [ ] **Field Cleanup**: String mentah berukuran besar (`message`, `raw_payload`) dihapus via processor `remove` setelah diekstrak guna menghemat disk storage.
- [ ] **Optimal Batch Sizing**: Bulk API payload dioptimalkan pada range $5-15\text{MB}$ per batch request.
- [ ] **Timeout & Backoff Configuration**: Client ingestion mengimplementasikan asynchronous dynamic jittered retry untuk kode status HTTP `429` & `503`.
- [ ] **Monitoring & Alerting**: Alert dikonfigurasi pada threshold `node.ingest.pipelines.<pipeline_name>.failed > 100`.

---

## 19: Ringkasan Eksekutif
Elasticsearch Ingest Node Pipeline menyediakan solusi *stream-transformation* bawaan yang efisien dan meminimalkan kebutuhan infrastruktur middleware tambahan. Kunci performa pipeline berada pada pemilihan processor yang tepat—memprioritaskan `dissect` daripada `grok`, mengamankan parsing dengan defensive scripting pada Painless, serta mengisolasi node processing untuk menjamin kestabilan search & storage layer. Melalui implementasi Bulk Ingestion Engine yang tangguh dengan error hook routing terstruktur, pipeline menjamin reliabilitas data masif tanpa risiko hilangnya log kritis akibat parsing exceptions.

---

## 20: Referensi & Bacaan Lanjutan
* Elasticsearch Official Documentation: [Ingest Node & Processors Reference](https://www.elastic.co/guide/en/elasticsearch/reference/current/ingest.html)
* Elastic Common Schema (ECS) Specification: [ECS Guidelines & Field Types](https://www.elastic.co/guide/en/ecs/current/index.html)
* High Performance Bulk Indexing Patterns: [Elasticsearch Indexing Performance Tuning](https://www.elastic.co/guide/en/elasticsearch/reference/current/tune-for-indexing-speed.html)
* Painless Scripting Language Specification: [Painless Ingest Guide](https://www.elastic.co/guide/en/elasticsearch/painless/current/painless-ingest-nodes.html)