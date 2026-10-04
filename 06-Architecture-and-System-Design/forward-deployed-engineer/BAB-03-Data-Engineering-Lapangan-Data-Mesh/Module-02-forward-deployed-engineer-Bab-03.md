# BAB 03: Data Engineering Lapangan & Data Mesh
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Arsitektur Data Product Node** secara mandiri menggunakan paradigma Data Mesh pada perimeter infrastruktur klien yang heterogen (On-Premises, Hybrid, Multi-Cloud).
- **Mengimplementasikan Federated Computational Governance** berbasis Open Policy Agent (OPA) dan OpenLineage untuk penegakan kebijakan keamanan data, kepatuhan GDPR/UU PDP, serta pelacakan silsilah data (*data lineage*) otomatis.
- **Membangun Runtime Data Contract Enforcement Engine** yang mampu mencegat schema drift, memvalidasi semantik payload secara real-time, dan mengisolasi anomali ke Dead Letter Queue (DLQ) tanpa menghentikan pemrosesan streaming.
- **Mengotomatisasi Provisioning Self-Serve Data Infrastructure** melalui abstraksi Infrastructure as Code (Terraform) untuk menyediakan penyimpanan analitik terisolasi berbasis Apache Iceberg/Object Storage dan query engine terdesentralisasi.
- **Mendiagnosis dan Menanggulangi Bottleneck Distribusi Data Lapangan** seperti network partition, metadata catalog locks, out-of-order event ingestion, dan degradasi performa I/O pada edge-to-cloud sync pipelines.

---

### 2. Prerequisites
Sebelum mendalami modul ini, peserta wajib menguasai:
- **Arsitektur Dasar Data Engineering**: Partisi data analitik, format columnar (Apache Parquet, ORC), query engine execution plan (Apache Spark, Trino/Presto, DuckDB).
- **Sistem Terdistribusi**: Teorema CAP, PACELC, konsistensi eventual vs. strong, protokol konsensus (Raft/Paxos basics).
- **Containerization & Orchestration**: Kubernetes lanjutan (Custom Resource Definitions/CRD, Operator pattern, NetworkPolicy, RBAC).
- **Bahasa Pemrograman**: 
  - Python (Tingkat lanjut: metaclasses, async I/O, Pydantic core internals, Arrow C Data Interface).
  - SQL (Window functions, query optimization, EXPLAIN plan analysis).
- **Penguasaan Modul 01**: Konsep dasar Forward Deployed Engineering, isolasi perimeter klien, dan fundamental domain-driven design pada data.

---

### 3. Concept & Internal Architecture (Mendalam)

Sebagai Forward Deployed Engineer (FDE), Anda tidak membangun data warehouse monolitik terpusat. Anda diterjunkan langsung ke domain bisnis klien untuk membangun simpul data (*data product node*) yang beroperasi di atas infrastruktur lokal mereka, namun terfederasi secara global.

```
       +------------------------------------------------------------------+
       |               FEDERATED COMPUTATIONAL GOVERNANCE                 |
       |  +--------------------+  +------------------+  +---------------+ |
       |  | OPA Engine (Rego)  |  | Catalog Registry |  |  OpenLineage  | |
       |  +---------+----------+  +--------+---------+  +-------+-------+ |
       +------------|----------------------|--------------------|---------+
                    |                      |                    |
                    v                      v                    v
+-------------------------------------------------------------------------------+
| DOMAIN DATA PRODUCT RUNTIME (Perimeter Klien)                                 |
|                                                                               |
|  +-------------------+       +-----------------------+                        |
|  | Upstream System   | ----> | INGESTION CONTROLLER  |                        |
|  | (OLTP / Event Bus)|       | (Debezium / Kafka)    |                        |
|  +-------------------+       +-----------+-----------+                        |
|                                          |                                    |
|                                          v                                    |
|                       +--------------------------------------+                |
|                       | CONTRACT VERIFICATION & DLQ ENGINE   |                |
|                       | - Schema Enforcement (Pydantic/Proto)|                |
|                       | - Semantic & Semantic Range Check    |                |
|                       +------------------+-------------------+                |
|                                          |                                    |
|                         +----------------+----------------+                   |
|                         | Valid Payload                   | Quarantine (DLQ)  |
|                         v                                 v                   |
|              +----------------------+          +--------------------+         |
|              | ICEBERG TABLE WRITER |          | OBJECT STORE DLQ   |         |
|              | (ACID Transactions)  |          | (Manual Triage)    |         |
|              +----------+-----------+          +--------------------+         |
|                         |                                                     |
|                         v                                                     |
|       +------------------------------------+                                  |
|       | LOCAL STORAGE LAYER (S3 / MinIO)   |                                  |
|       | Metadata (.avro) + Data (.parquet) |                                  |
|       +-----------------+------------------+                                  |
|                         |                                                     |
|                         v                                                     |
|       +------------------------------------+                                  |
|       | FEDERATED ACCESS INTERFACE (Trino) | <--- Authorized Consumers        |
|       | Policy Enforcement (Dynamic Mask)  |                                  |
|       +------------------------------------+                                  |
+-------------------------------------------------------------------------------+
```

#### Komponen Internal Data Product Node
1. **Contract Ingestion Gateway**: Komponen ingress data yang bertugas mengekstraksi raw events dari sistem operasional klien (CDC Debezium, EventStore, atau API). Gateway ini tidak melakukan mutasi bisnis, melainkan memverifikasi kepatuhan terhadap *Data Contract* sebelum data melangkah ke storage plane.
2. **Schema Registry & Semantic Interceptor**: Engine runtime lokal yang mengkomparasi struktur data yang masuk terhadap schema registry (v3/v4). Jika terdeteksi *breaking schema change* (misal tipe data integer diubah menjadi string tanpa backward compatibility), interceptor membelokkan payload secara deterministik ke *Quarantine/DLQ Storage* dan memicu alerting webhooks.
3. **Table Format Engine (Apache Iceberg)**: Storage engine yang memisahkan arsitektur fisik (Parquet files) dari interface lojik table. Iceberg mengelola *Snapshot Isolation*, *ACID Transactions*, serta *Hidden Partitioning*, menjamin query engine eksternal dapat membaca konsistensi data domain tanpa locking overhead.
4. **Federated Computational Governance Sidecar**: Agen (OPA-daemon + OpenLineage client) yang menginjeksi metadata operasional, mengecek hak otorisasi consumer berbasis token JWT/mTLS, dan menerapkan masking/filtering dinamis langsung pada level execution engine sebelum baris data meninggalkan perimeter domain.

---

### 4. Why & What

#### Why: Mengapa Arsitektur Ini Mutlak Diperlukan?
Model sentralisasi data tradisional (Data Lake/Warehouse terpusat) terbukti gagal pada skala enterprise multi-organisasi karena:
- **Bottleneck Tim Data Terpusat**: Tim analitik sentral tidak memahami konteks semantik dari database operasional tim penjualan atau sistem perbankan inti (*core banking*) klien.
- **Kerapuhan Pipeline ETL**: Perubahan satu kolom di basis data transaksi klien menyebabkan pipeline downstream gagal (*silent data corruption* atau *pipeline explosion*).
- **Kendala Regulasi & Kedaulatan Data**: Data finansial dan PII (Personally Identifiable Information) di yurisdiksi tertentu tidak diizinkan meninggalkan perimeter jaringan/infrastruktur asal domain untuk disatukan ke cluster raksasa global.

#### What: Karakteristik Solusi
Solusi ini menghadirkan simpul data otonom terstandarisasi yang:
- Memperlakukan data sebagai produk (*Data as a Product*) yang memiliki SLO/SLA, kepemilikan eksplisit (*domain ownership*), dan dokumentasi antarmuka publik yang dapat diakses melalui SQL/REST/gRPC.
- Menjamin data yang tersimpan telah divalidasi oleh kontrak yang tidak dapat dilanggar (*immutable contract*).
- Mendistribusikan beban komputasi dan pemeliharaan ke pemilik domain dengan tetap mempertahankan kendali federasi terpadu (katalog global, penegakan keamanan seragam).

---

### 5. How (Workflow Detail)

Alur kerja operasional end-to-end penanganan data di perimeter domain:

```
[Upstream Event]
       │
       ▼
[Ingestion Controller]
       │
       ▼
[Validate Against Contract] ───(Contract Breached?)───► [Write to DLQ Storage]
       │ No                                                    │
       ▼                                                       ▼
[Evaluate Governance Policies (OPA)]                  [Trigger PagerDuty/Alert]
       │
       ▼
[Inject OpenLineage Metadata Run Event]
       │
       ▼
[Commit Transaction to Iceberg Snapshot]
       │
       ▼
[Emit Catalog Metadata Update to Federated Registry]
       │
       ▼
[Consumer Trino Query Execution -> Dynamic Masking via OPA -> Read Result]
```

1. **Ingress**: Komponen ingress menerima batch payload data mentah (JSON/Avro) dari pipeline CDC domain.
2. **Schema Verification**: Engine mencocokkan event dengan Schema Contract (Protobuf/JSON Schema). Kompatibilitas divalidasi hingga level batasan tipe, range semantik, dan nullability.
3. **Branching**:
   - Jika *Invalid*: Event dikemas bersama metadata kesalahan (error code, violated rule, timestamp, upstream trace ID) dan ditulis ke DLQ Object Storage. Notifikasi dikirimkan ke domain engineer.
   - Jika *Valid*: Event dikonversi menjadi memori columnar Arrow RecordBatch.
4. **Governance Interception**: Open Policy Agent mengevaluasi aturan tagging klasifikasi data (misal: penandaan kolom PII seperti `email` atau `national_id`).
5. **Atomic Commit**: Batch ditulis ke dalam format Apache Parquet dan dikomit secara atomik ke snapshot Apache Iceberg lokal menggunakan optimistik concurrency control.
6. **Lineage Emission**: Engine memancarkan event `COMPLETE` ke OpenLineage backend (Marquez/DataHub) via HTTP async, memetakan transformasi dari source system ke snapshot Iceberg yang baru.
7. **Federated Query**: Konsumen internal maupun lintas domain mengakses data via Trino. Plugin OPA pada Trino membaca tag klasifikasi metadata dan melakukan dynamic hashing/masking secara on-the-fly sesuai identitas pemohon.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata
Bayangkan jaringan logistik ekspor-impor internasional. Model **Data Warehouse Terpusat** bagaikan memaksa seluruh komoditas global dari berbagai negara dikirim dalam kondisi mentah tanpa sortir ke satu pelabuhan raksasa tunggal di benua lain untuk dibersihkan, diinspeksi, dan dikemas ulang—menciptakan kemacetan masif, biaya tak terkendali, dan risiko kontaminasi massal.

Model **Data Mesh FDE** adalah jaringan **Zona Perdagangan Bebas Otonom**:
- Setiap negara (Domain) mengelola pabrik pengolahan standar sendiri (Data Product Node).
- Setiap produk wajib memiliki sertifikasi kualitas dan spesifikasi kemasan yang disepakati bersama (Data Contract).
- Barang rusak langsung ditolak dan dikarantina di pintu pabrik (DLQ), tidak pernah masuk kontainer ekspor.
- Otoritas pabean global menyediakan aturan keamanan dan pelacakan standar (Federated Computational Governance & Lineage), sementara barang tetap diproduksi dan disimpan secara terdesentralisasi hingga ada pembeli terverifikasi yang memesan.

#### Arsitektur Fisik Komponen (Node Infrastructure)

```
+-------------------------------------------------------------------------+
| WORKER NODE: worker-domain-payment-01                                   |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  | POD: data-product-engine                                          |  |
|  |                                                                   |  |
|  |  +------------------------------------+  +---------------------+  |  |
|  |  | Container: ingestion-contract-eval |  | Sidecar: opa-agent  |  |  |
|  |  | - Port: 8080 (Ingest API)          |  | - Port: 8181 (REST) |  |  |
|  |  | - Memory: 4Gi Limit                |  | - Rego Bundles Sync |  |  |
|  |  +-----------------+------------------+  +----------+----------+  |  |
|  |                    |                                |             |  |
|  |                    +--------------------------------+             |  |
|  |                                     |                             |  |
|  +-------------------------------------|-----------------------------+  |
|                                        v                                |
|  +-------------------------------------------------------------------+  |
|  | HOST-PATH / PERSISTENT VOLUME: Local Cache Engine                 |  |
|  | /var/data/staging-buffer/                                         |  |
|  +-------------------------------------+-----------------------------+  |
|                                        |                                |
+----------------------------------------|--------------------------------+
                                         v
         +----------------------------------------------------+
         | LOCAL OBJECT STORAGE (MinIO / Ceph S3 API)         |
         | s3://domain-payment-data-product/                  |
         | ├── metadata/                                      |
         | │   ├── v1.metadata.json                           |
         | │   └── snap-8392819028.avro                       |
         | ├── data/                                          |
         | │   └── partition_date=2024-10-24/data_01.parquet  |
         | └── dlq/                                           |
         |     └── failed_events_2024-10-24.json              |
         +----------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: In-Memory Contract Validation (Dasar Konsep)
Validasi sederhana menggunakan Pydantic untuk membendung schema drift sebelum data dialirkan.

```python
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime
from typing import Optional

class TransactionContractV1(BaseModel):
    transaction_id: str = Field(..., min_length=36, max_length=36)
    account_id: str = Field(..., min_length=10, max_length=20)
    amount: float = Field(..., gt=0.0)
    currency: str = Field(..., regex="^(IDR|USD|SGD)$")
    timestamp: datetime

raw_incoming_payload = {
    "transaction_id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
    "account_id": "ACC10029384",
    "amount": -500.0, # Pelanggaran Kontrak: Kurang dari 0.0
    "currency": "IDR",
    "timestamp": "2024-10-24T10:00:00Z"
}

try:
    validated_data = TransactionContractV1(**raw_incoming_payload)
    print("Payload valid. Menulis ke engine analitik.")
except ValidationError as e:
    print(f"[BLOCKED] Kontrak dilanggar! Arahkan ke DLQ:\n{e.json()}")
```

---

#### B. Practical Enterprise Example: Production-Grade Contract Engine & Iceberg Writer

Di bawah ini adalah implementasi pipeline produksi Python enterprise yang mencakup:
1. Validasi Data Contract berbasis semantik lanjutan.
2. Penegakan Dead Letter Queue (DLQ) bergaransi ketat jika validasi gagal.
3. Penulisan atomik ke format Apache Iceberg menggunakan katalog lokal/REST.
4. Instrumentasi pelacakan OpenLineage ke governance server.

```python
# File: domain_contract_processor.py
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import NoSuchTableError
from pyiceberg.schema import Schema
from pyiceberg.types import (
    DoubleType,
    NestedField,
    StringType,
    TimestampType,
)
from pydantic import BaseModel, Field, ValidationError, field_validator
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ContractEnforcementEngine")

# ============================================================================
# 1. DATA CONTRACT SPECIFICATION (Pydantic Layer)
# ============================================================================
class OrderEventContract(BaseModel):
    order_id: str = Field(..., min_length=10)
    customer_id: str = Field(..., min_length=5)
    amount: float = Field(..., gt=0.0)
    currency: str = Field(...)
    event_timestamp: datetime

    @field_validator("currency")
    @classmethod
    def validate_currency_allowed(cls, v: str) -> str:
        allowed = {"USD", "EUR", "IDR", "SGD"}
        if v not in allowed:
            raise ValueError(f"Mata uang {v} di luar domain whitelist: {allowed}")
        return v

    class Config:
        frozen = True

# ============================================================================
# 2. OPENLINEAGE EMITTER (Computational Governance Layer)
# ============================================================================
class OpenLineageTracker:
    def __init__(self, endpoint_url: str, job_name: str, namespace: str):
        self.endpoint_url = endpoint_url
        self.job_name = job_name
        self.namespace = namespace

    def emit_event(self, event_type: str, inputs: List[str], outputs: List[str], run_id: str, error: str = None):
        payload = {
            "eventType": event_type,
            "eventTime": datetime.now(timezone.utc).isoformat(),
            "run": {
                "runId": run_id,
                "facets": {
                    "errorMessage": {"message": error} if error else {}
                }
            },
            "job": {
                "namespace": self.namespace,
                "name": self.job_name
            },
            "inputs": [{"namespace": self.namespace, "name": inp} for inp in inputs],
            "outputs": [{"namespace": self.namespace, "name": out} for out in outputs],
            "producer": "https://github.com/enterprise/fde-domain-processor"
        }
        try:
            # Non-blocking telemetry emission
            requests.post(f"{self.endpoint_url}/api/v1/lineage", json=payload, timeout=2.0)
        except Exception as ex:
            logger.warning(f"Gagal memancarkan event OpenLineage: {ex}")

# ============================================================================
# 3. PRODUCTION STORAGE CONTROLLER (Apache Iceberg Layer)
# ============================================================================
class DomainDataProductStorage:
    def __init__(self, catalog_name: str, table_identifier: str, local_warehouse_dir: str):
        self.table_identifier = table_identifier
        # Menginisialisasi PyIceberg catalog (filesystem/SQLite backed untuk demonstrasi produksi isolated)
        self.catalog = load_catalog(
            catalog_name,
            **{
                "type": "sql",
                "uri": f"sqlite:///{local_warehouse_dir}/iceberg_catalog.db",
                "warehouse": f"file://{local_warehouse_dir}/warehouse",
            }
        )
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        schema = Schema(
            NestedField(field_id=1, name="order_id", field_type=StringType(), required=True),
            NestedField(field_id=2, name="customer_id", field_type=StringType(), required=True),
            NestedField(field_id=3, name="amount", field_type=DoubleType(), required=True),
            NestedField(field_id=4, name="currency", field_type=StringType(), required=True),
            NestedField(field_id=5, name="event_timestamp", field_type=TimestampType(), required=True),
        )
        try:
            self.table = self.catalog.load_table(self.table_identifier)
            logger.info(f"Iceberg Table '{self.table_identifier}' berhasil dimuat.")
        except NoSuchTableError:
            logger.warning(f"Table '{self.table_identifier}' tidak ditemukan. Membuat table baru...")
            self.table = self.catalog.create_table(
                identifier=self.table_identifier,
                schema=schema
            )
            logger.info(f"Iceberg Table '{self.table_identifier}' berhasil dibuat.")

    def write_records(self, valid_records: List[OrderEventContract]):
        if not valid_records:
            return

        arrow_data = {
            "order_id": [r.order_id for r in valid_records],
            "customer_id": [r.customer_id for r in valid_records],
            "amount": [r.amount for r in valid_records],
            "currency": [r.currency for r in valid_records],
            "event_timestamp": [r.event_timestamp for r in valid_records],
        }
        
        arrow_schema = pa.schema([
            ("order_id", pa.string()),
            ("customer_id", pa.string()),
            ("amount", pa.float64()),
            ("currency", pa.string()),
            ("event_timestamp", pa.timestamp('us', tz='UTC')),
        ])

        record_batch = pa.RecordBatch.from_pydict(arrow_data, schema=arrow_schema)
        arrow_table = pa.Table.from_batches([record_batch])
        
        # Eksekusi atomic overwrite/append snapshot
        self.table.append(arrow_table)
        logger.info(f"Kompilasi dan penulisan snapshot Iceberg berhasil: {len(valid_records)} record tersimpan.")

# ============================================================================
# 4. DEAD LETTER QUEUE (DLQ) CONTROLLER
# ============================================================================
class DeadLetterQueueManager:
    def __init__(self, dlq_file_path: str):
        self.dlq_file_path = dlq_file_path
        os.makedirs(os.path.dirname(self.dlq_file_path), exist_ok=True)

    def route_to_quarantine(self, raw_record: Dict[str, Any], validation_errors: List[Dict[str, Any]]):
        quarantine_entry = {
            "quarantine_id": str(uuid.uuid4()),
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "raw_payload": raw_record,
            "violations": validation_errors,
        }
        with open(self.dlq_file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(quarantine_entry) + "\n")
        logger.error(f"Event dialihkan ke DLQ! Quarantine ID: {quarantine_entry['quarantine_id']}")

# ============================================================================
# 5. CORE WORKFLOW PIPELINE RUNNER
# ============================================================================
class DomainDataIngestionPipeline:
    def __init__(self, storage: DomainDataProductStorage, dlq: DeadLetterQueueManager, lineage: OpenLineageTracker):
        self.storage = storage
        self.dlq = dlq
        self.lineage = lineage

    def process_batch(self, stream_messages: List[Dict[str, Any]]):
        run_id = str(uuid.uuid4())
        logger.info(f"Memulai pemrosesan batch. Run ID: {run_id}, Volume: {len(stream_messages)}")
        self.lineage.emit_event("START", ["kafka://order-cdc-raw"], [self.storage.table_identifier], run_id)

        valid_records: List[OrderEventContract] = []
        has_error = False

        for message in stream_messages:
            try:
                # Validasi kepatuhan terhadap data contract
                record = OrderEventContract(**message)
                valid_records.append(record)
            except ValidationError as err:
                has_error = True
                self.dlq.route_to_quarantine(message, err.errors())

        try:
            if valid_records:
                self.storage.write_records(valid_records)
            
            status = "COMPLETE" if not has_error else "COMPLETE_WITH_FAILURES"
            self.lineage.emit_event(status, ["kafka://order-cdc-raw"], [self.storage.table_identifier], run_id)
            logger.info("Batch lifecycle selesai dengan sukses secara operasional.")
        except Exception as ex:
            logger.critical(f"Kegagalan penulisan level penyimpanan: {ex}", exc_info=True)
            self.lineage.emit_event("FAIL", ["kafka://order-cdc-raw"], [self.storage.table_identifier], run_id, str(ex))
            raise ex


# ============================================================================
# RUNTIME INVOCATION (Uji Skenario Lapangan)
# ============================================================================
if __name__ == "__main__":
    BASE_DIR = "/tmp/fde_iceberg_node"
    
    storage_engine = DomainDataProductStorage(
        catalog_name="local_domain_catalog",
        table_identifier="payments.customer_orders",
        local_warehouse_dir=BASE_DIR
    )
    dlq_engine = DeadLetterQueueManager(f"{BASE_DIR}/dlq/orders_quarantine.jsonl")
    lineage_tracker = OpenLineageTracker(
        endpoint_url="http://localhost:5000", # Asumsi endpoint mock atau Marquez
        job_name="process_orders_contract_enforcement",
        namespace="domain_ecommerce_payments"
    )

    pipeline = DomainDataIngestionPipeline(storage_engine, dlq_engine, lineage_tracker)

    # Ingestion stream simulasi yang memuat record valid dan anomali kontraktual
    incoming_stream = [
        {
            "order_id": "ORD-109283-A",
            "customer_id": "CUST-992",
            "amount": 250000.0,
            "currency": "IDR",
            "event_timestamp": datetime.now(timezone.utc).isoformat()
        },
        {
            # Anomali: Nilai amount negatif dan currency ilegal
            "order_id": "ORD-ILLEGAL-01",
            "customer_id": "CUST-000",
            "amount": -10.0,
            "currency": "BITCOIN",
            "event_timestamp": datetime.now(timezone.utc).isoformat()
        },
        {
            "order_id": "ORD-109284-B",
            "customer_id": "CUST-411",
            "amount": 45.5,
            "currency": "USD",
            "event_timestamp": datetime.now(timezone.utc).isoformat()
        }
    ]

    pipeline.process_batch(incoming_stream)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Modernisasi Data Core Banking Tier-1
Sebuah bank multinasional memiliki sistem *Core Banking* berbasis mainframe dan basis data legacy Oracle yang melayani transaksi kartu kredit dan pinjaman di 4 negara. Tim sentral data lake mengalami backlog permintaan analitik rata-rata 5 bulan. Setiap ada rilis versi aplikasi perbankan, tabel analitik downstream selalu rusak akibat kolom yang dihapus atau diubah tipenya oleh tim operasional tanpa koordinasi.

#### Kendala Lapangan
1. **Peraturan Perbankan**: Data nasabah (PII) dilarang dipindahkan ke cloud global sebelum melewati proses de-identifikasi lokal.
2. **Ketergantungan Tim**: Tim domain core banking tidak mau menanggung beban pembuatan pipeline analitik kompleks, sementara tim sentral tidak tahu kalkulasi amortisasi pinjaman.

#### Implementasi Forward Deployed Engineering
1. **Penerapan Topologi Simpul Data Mesh**:
   - Tim FDE menanamkan data product node mandiri di OpenShift cluster internal perimeter tim perbankan.
   - Sumber upstream menggunakan Debezium CDC untuk membaca log transaksi Oracle tanpa membebani IOPS database produksi.
2. **Standardisasi Data Contract**:
   - Tim operasional domain dan tim analitik membuat repository schema contracts berbasis Protobuf v3.
   - Ingestion gateway domain mengompilasi schema tersebut ke dalam runtime checker. Jika ada rilis aplikasi internal yang mengubah kolom `account_status` menjadi numeric padahal kontraknya `string`, record tersebut langsung dialihkan ke DLQ lokal tanpa merusak pipeline konsumen.
3. **Federated Governance melalui Open Policy Agent (OPA)**:
   - Kebijakan perbankan ditulis ke dalam kode declarative (Rego).
   - Seluruh query Trino yang dialokasikan untuk data scientist secara otomatis mengaburkan (*pseudonymize*) kolom nomor kartu kredit (`card_number`) dan memotong digit saldo akun menjadi range segmentasi, kecuali dieksekusi oleh tim Audit Kepatuhan terotentikasi.

#### Hasil Terukur (Metrics & Key Results)
- **Time to Market Data Product**: Turun dari 5 bulan menjadi 4 hari kerja.
- **Pipeline MTBF (Mean Time Between Failures)**: Meningkat drastis dari kerusakan 3x per minggu menjadi 0 insiden dalam 6 bulan berturut-turut karena schema drift dicegat di pintu masuk isolasi contract engine.
- **Biaya Penyimpanan & Komputasi Sentral**: Turun 42% karena komputasi validasi dan penyimpanan operasional dilakukan di level cluster domain berbasis hardware komoditas.

---

### 9. Trade-offs (Analisis Arsitektur)

Memilih pendekatan Data Mesh dan Contract Enforcement terdistribusi mengharuskan FDE memperhitungkan trade-off struktural berikut:

| Parameter | Centralized Data Lake / Warehouse | Decentralized Domain Data Product (Mesh) | Justifikasi Rekayasa FDE |
| :--- | :--- | :--- | :--- |
| **Performance (Throughput)** | Sangat Tinggi (Bulk Microbatch write terpusat). | Moderat ke Tinggi (Validasi kontrak menambahkan parsing overhead di edge). | Validasi serde (serialization/deserialization) Pydantic/Protobuf mengorbankan 5-15% throughput CPU demi integritas data downstream. |
| **Ingestion Latency** | Jam hingga Harian (T/ELT terpusat). | Detik hingga Sub-detik (Event streaming langsung dari boundary domain). | Data segera tersedia untuk analytical consumption begitu lolos contract validator. |
| **Scalability (Organization)** | Lemah (Tergantung pada kapasitas scaling tim sentral). | Hampir Tak Terbatas (Skala terdistribusi mengikuti jumlah tim domain bisnis). | Domain independen mengalokasikan resource komputasi mereka sendiri tanpa bergantung antrean tiket pusat. |
| **Cost Matrix** | Biaya komputasi kluster terpusat sangat tinggi dan terkonsentrasi; storage murah. | Biaya komputasi menyebar (*distributed cost*); overhead infrastruktur redundan per-node (multi-tenant). | Mengharuskan implementasi self-serve infra automation agar overhead manajemen cluster terdesentralisasi tidak meledak. |
| **Governance & Lineage** | Mudah dikontrol secara manual karena lokasi tersentralisasi. | Sangat rumit tanpa tool otomatis (memerlukan Federated Automated Governance). | Wajib mengadopsi OpenLineage dan OPA agar konsistensi kebijakan tidak menjadi anarki operasional. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum Lapangan (Root Cause & Remediation)

##### 1. The Invisible Schema Drift (Silent Type Promotion)
- **Gejala**: Pipeline Python tidak crash, namun Trino memunculkan query error atau analitik menghasilkan metrik salah karena angka float presisi terpotong menjadi integer akibat deserializer default.
- **Penyebab**: Parser contract mengizinkan *type coercion* implisit (misal: `"123"` otomatis dikonversi jadi integer `123`).
- **Solusi**: Aktifkan mode ketat (*strict mode*) pada data contract validator (`strict=True` pada konfigurasi Pydantic) untuk menolak konversi tipe implisit.

##### 2. Snapshot Manifest Explosion pada Apache Iceberg
- **Gejala**: Latensi kueri terhadap data product meningkat eksponensial dari 200ms menjadi 30 detik dalam 2 minggu operasional.
- **Penyebab**: Ingestion pipeline melakukan *micro-commits* (misal commit per 50 event) ke tabel Iceberg, memicu pembuatan jutaan file metadata kecil dan Parquet berukuran kecil (*small files problem*).
- **Solusi**: Jadwalkan compact engine background process secara periodik:
  ```python
  # Menjalankan maintenance compaction via PyIceberg / Spark
  table.rewrite_data_files()
  table.expire_snapshots(older_than=retention_timestamp)
  ```

##### 3. Out-Of-Memory (OOM) pada Local Contract Interceptor
- **Gejala**: Container ingestion di Kubernetes mengalami status `OOMKilled` (Exit Code 137) saat beban traffic spike dari database CDC.
- **Penyebab**: Parsing payload array JSON berukuran masif langsung secara in-memory DOM model tanpa streaming deserializer.
- **Solusi**: Terapkan streaming batching menggunakan chunk read atau batas backpressure berbasis watermark window di memory boundary.

#### Skenario Troubleshooting Lapangan

**Skenario**: Consumer Trino mengeluhkan data pada tabel `payments.customer_orders` tertinggal 4 jam dari data operasional OLTP, tetapi container Ingestion Controller berstatus `Running`.

```bash
# LANGKAH 1: Masuk ke pod dan periksa throughput DLQ
kubectl logs -n domain-payment deployment/data-product-engine -c ingestion-contract-eval --tail=100

# Hasil temuan: Terlihat ribuan error logging validation failure
# ERROR: Event dialihkan ke DLQ! Field 'amount' violates min_range

# LANGKAH 2: Inspeksi isi file DLQ secara langsung
kubectl exec -it -n domain-payment deployment/data-product-engine -c ingestion-contract-eval -- \
  tail -n 5 /tmp/fde_iceberg_node/dlq/orders_quarantine.jsonl | jq .

# Analisis: Ditemukan bahwa upstream service melepaskan pembaruan yang mengubah field "amount"
# yang sebelumnya berupa absolute number menjadi format object bertingkat: {"value": 2500.0, "currency_code": "IDR"}

# LANGKAH 3: Remediasi Tindakan FDE
# 1. Rollback upstream change ATAU
# 2. Terbitkan Contract Version 2 (OrderEventContractV2) yang mendukung nested amount.
# 3. Jalankan replay tool untuk memproses ulang payload dari DLQ ke storage.
```

---

### 11. Best Practices (Production Checklist)

Gunakan tabel ini sebagai evaluasi kesiapan rilis Data Product Node sebelum diserahterimakan ke tim domain klien:

| Kategori | Item Checklist | Status Kesiapan |
| :--- | :--- | :--- |
| **Contract** | Semua field bertipe data eksplisit tanpa fallback `Any`. | [ ] Mandatory |
| **Contract** | Schema versioning terdaftar di Semantic Registry (v1, v2, ...). | [ ] Mandatory |
| **Resilience** | DLQ memiliki kapasitas storage persisten mandiri terpisah dari buffer memory. | [ ] Mandatory |
| **Resilience** | Mekanisme Circuit Breaker aktif jika error rate DLQ melebihi 10% dalam 5 menit. | [ ] Mandatory |
| **Storage** | Compaction job (bin-packing) aktif untuk mencegah small-files disaster. | [ ] Mandatory |
| **Storage** | Snapshot retention diatur maksimum 7 hari untuk meminimalkan beban metadata. | [ ] Mandatory |
| **Governance** | OpenLineage memancarkan event START, COMPLETE, dan FAIL ke centralized catalog. | [ ] Mandatory |
| **Governance** | Masking PII telah divalidasi via OPA policies pada federated engine. | [ ] Mandatory |
| **Observability**| Metrik Prometheus diekspor: `records_ingested_total`, `contract_violations_total`. | [ ] Mandatory |

---

### 12. Hands-on Practice

Struktur direktori kerja praktikum:
```text
hands-on/m02/
├── contracts/
│   └── order_contract.json
├── terraform/
│   └── main.tf
├── src/
│   ├── app.py
│   └── requirements.txt
└── test_data/
    ├── batch_good.json
    └── batch_corrupted.json
```

#### Langkah 1: Persiapan Environment
Buat file `hands-on/m02/src/requirements.txt`:
```text
pyiceberg==0.6.1
pyarrow==15.0.2
pydantic==2.6.4
requests==2.31.0
pytest==8.1.1
```
Jalankan instalasi:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r hands-on/m02/src/requirements.txt
```

#### Langkah 2: Terraform Abstraction untuk Local MinIO & Metadata (Self-Serve Data Platform)
Buat file `hands-on/m02/terraform/main.tf` untuk mem-provision storage bucket analitik domain lokal:

```hcl
terraform {
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}

variable "domain_name" {
  type    = string
  default = "payment-domain"
}

# Membuat direktori lokal yang bertindak sebagai mock S3/Warehouse storage
resource "local_file" "init_warehouse" {
  filename = "${path.module}/../../hands-on/m02/warehouse/${var.domain_name}/.keep"
  content  = "# Initialized Domain Storage for Iceberg"
}

output "domain_storage_path" {
  value = "${path.module}/../../hands-on/m02/warehouse/${var.domain_name}"
}
```
Inisialisasi Terraform:
```bash
cd hands-on/m02/terraform
terraform init
terraform apply -auto-approve
cd ../../..
```

#### Langkah 3: Menguji Penolakan Kontrak dan Penulisan Data
Buat payload pengujian `hands-on/m02/test_data/batch_corrupted.json`:
```json
[
  {
    "order_id": "ORD-PERFECT-01",
    "customer_id": "CUST-883",
    "amount": 750000.0,
    "currency": "IDR",
    "event_timestamp": "2024-10-24T12:00:00Z"
  },
  {
    "order_id": "ORD-BAD-02",
    "customer_id": "CUST-UNKNOWN",
    "amount": -99999.0,
    "currency": "YEN",
    "event_timestamp": "2024-10-24T12:05:00Z"
  }
]
```

Jalankan script verifikasi menggunakan source code dari sub-bab **7.B**:
```bash
python hands-on/m02/src/app.py
```
Periksa bahwa:
1. File `orders_quarantine.jsonl` menangkap event `ORD-BAD-02`.
2. Snapshot SQLite/Iceberg catalog hanya mencatat 1 row (`ORD-PERFECT-01`).

---

### 13. Exercises

#### Level Easy
**Tugas**: Tambahkan validasi pada `OrderEventContract` di kode Python agar kolom `order_id` harus diawali dengan prefix `"ORD-"`. Event yang tidak menggunakan prefix harus dilempar ke DLQ.
- **Kriteria Penerimaan**:
  - Validasi regex berhasil menangkap format tanpa prefix.
  - Event yang valid tetap tertulis ke database analitik tanpa error.

#### Level Medium
**Tugas**: Implementasikan circuit breaker sederhana pada `DomainDataIngestionPipeline`. Jika persentase event yang gagal masuk DLQ melebihi 50% dari total satu batch (minimum batch size = 10), pipeline harus menghentikan proses (*halt*), membatalkan seluruh snapshot Iceberg pada batch tersebut, dan melempar exception `DataContractBreachException`.
- **Kriteria Penerimaan**:
  - Menghindari *partial commit* yang merusak integritas analitik.
  - Snapshot Iceberg tidak bertambah jika circuit breaker terpicu.

#### Level Hard
**Tugas**: Buat modul sinkronisasi metadata Iceberg yang mengekspor schema terupdate ke server OpenLineage secara otomatis setiap kali ada snapshot commit baru. Modul harus mengekstraksi skema PyArrow (`field_names` dan `field_types`) dan membangun facet `schema` sesuai standar OpenLineage Schema Dataset Facet.
- **Kriteria Penerimaan**:
  - Payload POST HTTP terkirim ke target mock HTTP receiver.
  - Skema metadata cocok 100% dengan definisi kolom di Iceberg table.

---

### 14. Challenge

#### Deskripsi Tantangan Lapangan (Air-Gapped Core Settlement Desynchronization)
Anda diterjunkan ke bank sentral regional yang menerapkan topologi **Data Mesh Air-Gapped**. Klien memiliki dua environment:
1. **Network Zone A (Core Transaction - Restricted On-Prem)**: Sumber transaksi finansial settlement real-time. Tidak memiliki akses internet, tidak boleh diakses oleh Trino sentral.
2. **Network Zone B (Analytics DMZ - Cloud)**: Tempat para data consumer dan data scientist mengeksekusi analytical queries federasi.

Antara Zone A dan Zone B hanya ada one-way data diode (UDP diode unidirectional) dengan MTU terbatas dan potensi paket hilang (*unreliable transport*) sebesar 0.1%. Diode hanya mengizinkan pengiriman file batch per 1 menit tanpa ada jalur balik (*zero acknowledgement backchannel*).

Tiba-tiba, tim audit menemukan bahwa data analitik di Zone B mengalami deviasi agregat nilai finansial sebesar 1.4% dibanding Zone A. Konsumen analitik terus memproses data tanpa menyadari adanya partisi data yang hilang atau rusak saat menembus data diode.

#### Sasaran Tugas:
Rancang dan susun arsitektur simpul data (*data product node deployment*) yang:
1. Menjamin integritas matematis data analitik di Zone B menggunakan arsitektur verifikasi desentralisasi tanpa komunikasi dua arah (*bidirectional handshake* dilarang oleh hardware diode).
2. Membangun mekanisme rekonsiliasi state berbasis cryptographic proof (Merkle Tree / Hash Chaining) yang disematkan ke dalam metadata Iceberg table pada Zone A dan dievaluasi di Zone B.
3. Mengembangkan skema alerting pada federated query interface Trino di Zone B sehingga kueri analitik otomatis di-block jika cryptographic checkpoint menunjukkan data tidak lengkap (*incomplete snapshot state*).

*Sajikan diagram topologi arsitektur sistem, rancangan manifest metadata, dan implementasi core validation logic.*

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)
1. **Apa perbedaan mendasar antara Data Mesh dan arsitektur Data Lake tersentralisasi?**
   - *Jawaban*: Data Lake memusatkan kepemilikan data, penyimpanan, dan pemrosesan pada satu tim sentral monolitik. Data Mesh mendesentralisasikan kepemilikan ke domain bisnis yang memproduksi data, memperlakukan data sebagai produk, dan mengandalkan federated computational governance.
2. **Apa yang dimaksud dengan Data Contract dalam konteks Data Product?**
   - *Jawaban*: Perjanjian formal antara produsen data (domain) dan konsumen data yang mendefinisikan skema struktur, semantik data, batasan bisnis, SLA, dan penanganan evolusi skema (*schema evolution*) yang ditegakkan secara programmatic.
3. **Mengapa format tabel seperti Apache Iceberg lebih diutamakan daripada direktori Parquet biasa dalam Data Mesh?**
   - *Jawaban*: Iceberg menyediakan ACID snapshot isolation, dynamic metadata tracking, time-travel queries, dan hidden partitioning yang mencegah data consumer membaca data yang corrupt atau setengah-tertulis selama ingestion berlangsung.
4. **Apa peran Dead Letter Queue (DLQ) dalam pipeline verifikasi kontrak data?**
   - *Jawaban*: DLQ mengisolasi record yang melanggar kontrak skema atau integritas bisnis ke storage terpisah untuk inspeksi teknis tanpa menghentikan kelangsungan aliran ingest record lain yang valid.
5. **Bagaimana peran Open Policy Agent (OPA) dalam Federated Governance?**
   - *Jawaban*: OPA bertindak sebagai policy decision engine terdistribusi yang mengevaluasi aturan akses, masking kolom sensitif (PII), dan perizinan kueri secara konsisten di seluruh domain node menggunakan deklarasi bahasa Rego.

#### B. Pertanyaan Intermediate (5 Soal)
6. **Bagaimana Data Product Node menangani breaking schema changes tanpa memutus downstream consumer yang masih memakai schema lama?**
   - *Jawaban*: Melalui versioning schema paralel (multi-version contract). Node menyediakan antarmuka atau view terpisah (misal: v1 dan v2) di catalog. Produsen memancarkan format v2, sementara ingestion layer melakukan translasi otomatis/kompatibilitas mundur atau mengekspos logical dataset v1 dan v2 secara simultan.
7. **Mengapa penegakan kontrak data sebaiknya dilakukan sedekat mungkin dengan boundary domain penghasil data daripada di central data lake?**
   - *Jawaban*: Untuk mencegah degradasi data (*data pollution*) masuk ke ekosistem analitik. Masalah integritas langsung diselesaikan oleh tim domain yang paham konteks bisnisnya sebelum data teragregasi secara ambigu di hilir.
8. **Jelaskan risiko small files problem pada penulisan Apache Iceberg di arsitektur streaming dan bagaimana cara menanggulanginya!**
   - *Jawaban*: Ingestion berlatensi rendah memicu penulisan file Parquet berukuran kecil dalam jumlah masif ke object store, mengakibatkan metadata membengkak dan query latency anjlok. Mitigasinya adalah menjalankan asynchronous compaction engine yang menggabungkan file-file kecil menjadi ukuran optimal (~128MB - 512MB) tanpa mengunci tabel.
9. **Bagaimana cara kerja Dynamic Data Masking pada integrasi Trino dan Open Policy Agent?**
   - *Jawaban*: Saat query dikirimkan ke Trino, plugin Trino OPA interceptor mengirim identitas user (role, groups) dan target columns ke OPA. OPA mengembalikan policy instructions. Jika user tidak authorized, Trino rewrite abstract syntax tree (AST) kueri secara real-time untuk membungkus kolom target dengan fungsi enkripsi/hash (e.g., `SHA256(col)` atau `'XXXX-XXXX'`) sebelum dieksekusi.
10. **Apa perbedaan semantic drift dan structural schema drift?**
    - *Jawaban*: Structural schema drift berkaitan dengan format teknis (kolom dihapus, diganti tipe data dari integer ke string). Semantic drift terjadi ketika format teknis tetap sama, namun arti bisnisnya berubah drastis (contoh: kolom `discount_price` yang awalnya menyimpan nilai diskon absolut diganti menjadi persentase tanpa ada perubahan nama atau tipe data kolom).

#### C. Skenario Kasus Produksi (3 Soal)

11. **Skenario Kasus 1: Mengatasi Ledakan Lock Metadata pada Concurrent Writing**
    - *Konteks*: Tiga sub-domain pipeline menulis secara simultan ke tabel Iceberg yang sama pada lokal storage node dengan micro-batching 10 detik. Ingestion sering mengalami error `CommitFailedException: Branch commit conflict: current snapshot has moved`.
    - *Analisis Tindakan FDE*:
      1. Terapkan exponential backoff dan jitter retry pada transaksi commit Iceberg.
      2. Re-evaluasi pemodelan domain: Jika tiga sub-domain menulis ke tabel yang sama secara konkuen, domain boundaries kemungkinan besar salah dipetakan. Pecah tabel menjadi data product independen per domain dan gabungkan di consumer level via logical join view di Trino.
      3. Jika penggabungan wajib di level penulisan, pisahkan lokasi partisi fisik data per-subdomain sehingga Iceberg dapat melakukan non-conflicting snapshot commit.

12. **Skenario Kasus 2: Penegakan Kepatuhan Cross-Border Data Transfer (UU PDP / GDPR)**
    - *Konteks*: Data Product Node domain finansial di Indonesia perlu diekspos ke HQ di Frankfurt untuk analitik agregat regional, namun UU PDP lokal melarang nomor identitas kependudukan (KTP) dan nomor rekening nasabah dikirim keluar yurisdiksi.
    - *Analisis Tindakan FDE*:
      1. Buat data contract baru khusus konsumsi eksternal (e.g., `regional_financial_summary_v1`).
      2. Konfigurasikan OPA policy agent lokal di data product node untuk menolak ekspor raw level data.
      3. Di tingkat storage node lokal, sediakan pre-aggregated view yang melakukan k-anonymity atau differential privacy terhadap transaksi keuangan nasabah, sehingga dataset yang keluar dari perimeter Indonesia sudah berbentuk metadata agregat tanpa jejak PII individual.

13. **Skenario Kasus 3: Schema Poisoning Akibat Influx CDC Out-of-Order**
    - *Konteks*: Upstream Debezium CDC dari MariaDB mereplikasi event transaksi pembayaran. Jaringan mengalami network glitch, sehingga event `DELETE` atau `UPDATE` tiba lebih dulu di data contract engine sebelum event `CREATE` (Out-of-Order). Akibatnya, validasi contract gagal karena `order_id` yang direferensikan belum terdaftar, membanjiri DLQ dengan false-positive errors.
    - *Analisis Tindakan FDE*:
      1. Jangan langsung membuang record ke DLQ murni. Implementasikan runtime staging state storage lokal (menggunakan RocksDB atau Redis cluster lokal) dengan sliding time-window TTL buffer (misal 5 menit).
      2. Event CDC diurutkan kembali berbasis database source commit timestamp (`ts_ms`) dan Log Sequence Number (LSN/GTID) sebelum divalidasi ke contract engine.
      3. Jika window TTL habis dan parent record tetap tidak muncul, baru arahkan event tersebut ke DLQ dengan error tag eksplisit: `ORPHAN_CHILD_EVENT_TIMEOUT`.

---

### 16. Summary

- **Forward Deployed Engineer (FDE)** di ranah Data Mesh bertindak sebagai arsitek dan implementor garis depan yang membangun boundary otonom di perimeter infrastruktur klien menggunakan paradigma *Data as a Product*.
- **Data Contracts** bukan sekadar skema statis, melainkan komponen software runtime terdistribusi yang secara tegas memisahkan tanggung jawab produsen data dan menjamin zero schema drift downstream melalui automated quarantine routing (DLQ).
- **Federated Computational Governance** mengotomatisasi interoperabilitas, silsilah operasional (OpenLineage), dan penegakan regulasi kepatuhan (OPA dynamic masking) tanpa memusatkan kembali beban operasional data pipeline ke tim pusat.
- **Implementasi Apache Iceberg** pada simpul terdesentralisasi memberikan kekuatan ACID transactions, snapshot isolation, dan performa query analitik modern langsung di level storage domain, mengeliminasi kerapuhan distributed file layout konvensional.