# BAB 09: Shift-Left Data Quality, Testing & Contract Enforcement
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Merancang Arsitektur Data Contract Enterprise** menggunakan spesifikasi deklaratif modern (*Open Data Contract Standard* / ODCS) yang menjembatani domain produsen (*software engineering*) dan konsumen (*analytics/AI engineering*).
2. **Mengimplementasikan Mekanisme Validasi In-line dan CI/CD Shift-Left** untuk mencegah *breaking schema changes* dan degradasi semantik sebelum data masuk ke *landing zone* atau *event broker*.
3. **Membangun Automated Data Quarantine Pattern & Circuit Breaker** pada *streaming* dan *batch ingestion engine* guna mengisolasi anomali data tanpa menghentikan pemrosesan data valid (*zero-downtime fault tolerance*).
4. **Mengintegrasikan Automated Data Quality Testing Frameworks** (Great Expectations Fluent API / Soda Core) ke dalam *orchestration runtime* dan *event-driven architecture*.
5. **Mengukur dan Mengevaluasi Trade-offs** antara latensi komputasi, *throughput*, biaya infrastruktur, dan ketahanan data (*robustness*) dalam ekosistem skala petabyte.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Distributed Streaming & Messaging:** Apache Kafka (pemahaman mendalam tentang *Serialization/Deserialization*, Avro/Protobuf/JSON Schema, *Schema Registry compatibility modes*: BACKWARD, FORWARD, FULL).
- **Modern Data Warehousing & Lakehouse:** Arsitektur Medallion (Bronze/Silver/Gold) menggunakan Apache Iceberg atau Delta Lake.
- **Data Modeling & Transformation:** SQL tingkat lanjut, dbt (*data build tool*) konsep *tests*, *snapshots*, dan *semantic layer*.
- **CI/CD & DevOps Engineering:** Git workflow, GitHub Actions/GitLab CI, Docker containerization.
- **Python Engineering:** Python 3.10+, OOP tingkat lanjut, Pydantic v2, *typing*, dan integrasi API testing.

---

### 3. Concept & Internal Architecture

Implementasi konvensional menempatkan pengujian kualitas data di hilir (*downstream*), setelah data mendarat di Data Warehouse. Pendekatan reaktif ini menyebabkan *silent data corruption*, rusaknya metrik finansial, dan kegagalan model Machine Learning di produksi. 

*Shift-Left Data Quality* memindahkan tanggung jawab integritas data sedekat mungkin ke hulu (*producer domain*). Inti dari pendekatan ini bertumpu pada **Data Contract** sebagai artefak hukum (*contractual enforcement*) antara produsen dan konsumen data.

```
+---------------------------------------------------------------------------------------+
|                                    CONTROL PLANE                                      |
|                                                                                       |
|  +------------------------+      PR Check / Push       +---------------------------+  |
|  | Producer Microservice  |--------------------------->| CI/CD Pipeline Contract   |  |
|  | Git Repo (Domain Team) |                            | Linter & Breaking Detector|  |
|  +------------------------+                            +-------------+-------------+  |
|              |                                                       |                |
|              v Semantic & Schema Sync                                v Schema Push    |
|  +-------------------------------------------------------------------+-------------+  |
|  | Data Contract Registry (ODCS Specification / Central Schema Catalog / DataHub)  |  |
|  +-------------------------------------------------------------------+-------------+  |
+----------------------------------------------------------------------|----------------+
                                                                       |
+----------------------------------------------------------------------v----------------+
|                                     DATA PLANE                                        |
|                                                                                       |
|   +-----------------------+     Produce Event       +-----------------------------+   |
|   |  Producer Application |------------------------>| Outbox CDC / API Gateway    |   |
|   |  (Pydantic/Avro Serial|                         | In-line Contract Validator  |   |
|   +-----------------------+                         +--------------+--------------+   |
|                                                                    |                  |
|                                                Pass Validation     | Fail Validation  |
|                                            +-----------------------+--------------+   |
|                                            v                                      v   |
|                                  +-------------------+                  +-----------+ |
|                                  | Core Kafka Topic  |                  | DLQ /     | |
|                                  | (Valid Stream)    |                  | Quarantine| |
|                                  +---------+---------+                  +-----+-----+ |
|                                            |                                  |       |
|                                            v                                  v       |
|                            +-------------------------------+          +-------------+ |
|                            | Stream / Batch Ingestion      |          | Dead Letter | |
|                            | (Flink / Spark / Delta / Ice) |          | Store (S3/  | |
|                            +---------------+---------------+          | GCS Bucket) | |
|                                            |                          +-------------+ |
|                                            v Contract Enforcement                     |
|                            +-------------------------------+                          |
|                            | Silver Layer Tables           |                          |
|                            | (Enriched & Schema Compliant) |                          |
|                            +-------------------------------+                          |
+---------------------------------------------------------------------------------------+
```

#### Komponen Internal Arsitektur Data Contract:

1. **Contract Definition Engine:**
   Menggunakan format standar seperti ODCS (Open Data Contract Standard) berbasis YAML. Komponen ini mendefinisikan skema fisik (*types*, *nullability*), semantik (*business logic, domain entities*), *Service Level Agreements* (SLA: *freshness*, *latency*), dan aturan kepatuhan privasi (GDPR/masking).
2. **Static Contract Linter & Breaking Change Engine:**
   Bekerja pada tahap CI/CD produsen. Menganalisis perubahan skema kode aplikasi terhadap kontrak yang aktif. Mencegah *breaking changes* seperti menghapus kolom, mengubah tipe data *primitive* (misal: `int64` ke `string`), atau memperketat *nullability* tanpa *major version increment*.
3. **In-line Enforcement Interceptor:**
   Layer validasi yang disematkan pada *serialization step* di Producer SDK, Outbox Pattern Processor, atau Consumer Ingestion Gateway. Validasi mengeksekusi dua layer pengecekan:
   - *Structural Verification:* Pengecekan tipe biner/JSON terhadap skema registri.
   - *Semantic Assertions:* Pengecekan aturan deterministik (misal: `amount > 0`, `currency IN ('IDR', 'USD')`).
4. **Dynamic Circuit Breaker & Quarantine Router:**
   Jika sebuah mutasi data melanggar kontrak, *ingestion engine* tidak mematikan *cluster* secara fatal (*catastrophic crash*), melainkan membelokkan (*divert*) payload yang rusak ke *Dead Letter Queue* (DLQ) atau *Quarantine Storage Partition* lengkap dengan *metadata audit trail* (alasan kegagalan, *timestamp*, *payload dump*).

---

### 4. Why & What

| Dimensi | Pendekatan Reaktif Tradisional | Shift-Left Enterprise Contract |
| :--- | :--- | :--- |
| **Lokasi Deteksi** | Data Warehouse / Dashboard Downstream | Producer Repo (CI/CD) & Ingestion Gateway |
| **Metode Penanganan** | Data engineer menulis patch SQL manual / backfill darurat | Circuit breaker memblokir payload; sistem hulu diberi notifikasi otomatis |
| **Ownership** | Sentralisasi tim Data Platform (Silo) | Domain-driven: Tim Software Engineer pemilik domain |
| **Dampak Schema Drift** | Pipeline rusak, data analitik/ML hallucination | Skema terisolasi, perubahan skema terikat *versioning system* (SemVer) |
| **Mean Time to Detect (MTTD)** | Berhari-hari hingga berminggu-minggu | Sub-detik (*real-time*) atau pada saat *Pull Request* |

#### Mengapa Perlu In-line Contract Enforcement?
Jika terjadi perubahan tak terduga (*schema drift*) di hulu (misal: tim Checkout mengubah format `order_id` dari UUID string menjadi Integer auto-increment), pipeline downstream yang memproses ribuan partisi Delta Lake akan gagal di tahap de-serialisasi. Perbaikan *post-hoc* membutuhkan *backfilling* jutaan data yang mahal dan memakan waktu komputasi intensif. Shift-left mencegah data non-konformatif masuk ke sistem penyimpanan persisten downstream.

---

### 5. How (Workflow Detail)

Alur kerja operasional integrasi Data Contract:

```
[Developer Modifikasi Skema]
               │
               ▼
[Pre-commit Hook / Local Test] ──(Validasi lokal via ODCS CLI)
               │
               ▼
[Git Push -> CI Pipeline]
       │
       ├─► Task 1: Check ODCS Schema Syntax
       ├─► Task 2: Schema Compatibility Check vs Central Registry
       └─► Task 3: Dry-run Consumer Integration Tests
               │
      (Lulus Validasi?)
         ├── TIDAK ──► [Block PR / Push Failure Notification]
         └── YA
               │
               ▼
[CD Step: Register New Schema Version (State: DRAFT/ACTIVE)]
               │
               ▼
[Producer Runtime: Emitting Data]
       │
       ├─► Producer Serializer menerapkan Contract Validation
       │
      (Valid Payload?)
         ├── TIDAK ──► [Kirim ke Quarantine Queue / DLQ] ──► [PagerDuty Alert]
         └── YA
               │
               ▼
[Event Broker (Kafka/Redpanda)]
               │
               ▼
[Downstream Processing: Spark/Flink/dbt]
       │
       ├─► Check Ingestion Assertions (Great Expectations/Soda)
       └─► Upsert ke Medallion Engine (Iceberg/Delta)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Inspeksi Pabrik Komponen Otomotif
Bayangkan industri manufaktur mobil. 
- **Pendekatan Tradisional (Post-hoc):** Baut dan mur dari vendor dipasang langsung ke mobil sampai mobil selesai dirakit. Di ujung pabrik, saat uji jalan, mesin meledak karena ukuran baut salah 1 milimeter. Anda harus membongkar seluruh mobil (mahal, lambat, berbahaya).
- **Pendekatan Shift-Left (Contract Enforcement):** Vendor baut diberi cetak biru resmi (*Data Contract*). Sebelum truk vendor masuk ke gerbang pabrik (*Ingestion*), sebuah sensor laser presisi (*In-line Validator*) mengukur setiap baut. Baut yang meleset 0.1 mm langsung disingkirkan ke keranjang karantina (*Quarantine DLQ*), sementara alarm pabrik otomatis mengirim surat peringatan ke vendor. Pabrik mobil tetap beroperasi tanpa henti.

#### Arsitektur Deep Dive Isolasi Karantina:

```
                       INCOMING EVENT STREAM
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ Consumer / Stream App │
                     └───────────┬───────────┘
                                 │
                 Validate against Data Contract
                                 │
            ┌────────────────────┴────────────────────┐
     [Schema Valid]                           [Schema Invalid / Broken]
            │                                         │
            ▼                                         ▼
 ┌───────────────────────┐                 ┌───────────────────────┐
 │ Transformation Engine │                 │ Quarantine Decorator  │
 │ (Spark Structured /   │                 │ Inject Error Context: │
 │ Flink Job)            │                 │ - raw_payload         │
 └──────────┬────────────┘                 │ - failure_reason      │
            │                              │ - violation_timestamp │
            ▼                              │ - producer_service    │
 ┌───────────────────────┐                 └──────────┬────────────┘
 │ Production Storage    │                            │
 │ Table: Orders         │                            ▼
 │ Format: Apache Iceberg│                 ┌───────────────────────┐
 └───────────────────────┘                 │ Quarantine Lake Table │
                                           │ Path: /quarantine/    │
                                           │ orders_violation/     │
                                           └───────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Menguji Dataframe dengan Python Contract Validator Sederhana
Menggunakan Pydantic untuk membendung *breaking change* sebelum masuk ke pipeline.

```python
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError
from typing import Literal

# Contract Specification via Pydantic
class PaymentEventContract(BaseModel):
    event_id: str = Field(..., min_length=36, max_length=36)
    timestamp: datetime
    amount: float = Field(..., gt=0.0)
    currency: Literal["IDR", "USD", "SGD"]
    customer_id: str

# Payload dari producer
payload_valid = {
    "event_id": "c4b3f88a-9f5e-4c7b-871d-19cbfce4d241",
    "timestamp": "2024-03-30T10:00:00Z",
    "amount": 250000.50,
    "currency": "IDR",
    "customer_id": "CUST-9921"
}

payload_invalid = {
    "event_id": "invalid-uuid",
    "timestamp": "2024-03-30T10:00:00Z",
    "amount": -500.0, # Pelanggaran Semantik
    "currency": "EUR", # Pelanggaran Skema
    "customer_id": "CUST-9921"
}

def process_event(raw_data: dict) -> None:
    try:
        validated_data = PaymentEventContract(**raw_data)
        print(f"SUCCESS: Event {validated_data.event_id} diproses.")
    except ValidationError as e:
        print(f"CIRCUIT BREAKER: Data ditolak. Detail: {e.errors()}")

process_event(payload_valid)
process_event(payload_invalid)
```

#### Practical Example: Enterprise In-Line Stream Validator & Quarantine Routing
Script produksi berikut mensimulasikan worker ingestion Kafka yang mengeksekusi validasi kontrak semantik dan structural schema, memisahkan data bersih (*Bronze/Silver*) dan data rusak (*Quarantine DLQ*) menggunakan OpenDataContract semantics.

```python
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from jsonschema import Draft202012Validator, exceptions

# Setup Logging Industri
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EnterpriseContractEnforcer")

# 1. Definisi Data Contract (Schema & Business Rules)
ORDER_CONTRACT_SPEC: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "OrderPlacedEventContract",
    "type": "object",
    "properties": {
        "order_id": {"type": "string", "pattern": "^ORD-[0-9]{8}$"},
        "account_id": {"type": "string", "format": "uuid"},
        "order_timestamp": {"type": "string", "format": "date-time"},
        "total_amount": {"type": "number", "minimum": 1000.0},
        "items_count": {"type": "integer", "minimum": 1, "maximum": 50},
        "payment_status": {"type": "string", "enum": ["PENDING", "SETTLED", "REJECTED"]}
    },
    "required": ["order_id", "account_id", "order_timestamp", "total_amount", "items_count", "payment_status"],
    "additionalProperties": False  # Mencegah payload disusupi kolom sampah/undocumented
}

@dataclass(frozen=True)
class QuarantineEnvelope:
    raw_payload: str
    failure_reasons: List[str]
    violation_timestamp: str
    producer_service: str
    contract_target: str

class DataContractEnforcementEngine:
    def __init__(self, contract_schema: Dict[str, Any], producer_name: str):
        self.validator = Draft202012Validator(contract_schema)
        self.contract_name = contract_schema.get("title", "UnknownContract")
        self.producer_name = producer_name

    def validate_and_route(self, raw_message: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[QuarantineEnvelope]]:
        errors = []
        parsed_json = None
        
        # Phase 1: Structural Parsing Verification
        try:
            parsed_json = json.loads(raw_message)
        except json.JSONDecodeError as err:
            errors.append(f"Malformed JSON Syntax: {str(err)}")
            quarantine_record = QuarantineEnvelope(
                raw_payload=raw_message,
                failure_reasons=errors,
                violation_timestamp=datetime.now(timezone.utc).isoformat(),
                producer_service=self.producer_name,
                contract_target=self.contract_name
            )
            return False, None, quarantine_record

        # Phase 2: Schema & Semantic Contract Validation
        validation_errors = sorted(self.validator.iter_errors(parsed_json), key=lambda e: e.path)
        if validation_errors:
            for err in validation_errors:
                field_path = ".".join([str(p) for p in err.path]) if err.path else "root"
                errors.append(f"Field '{field_path}': {err.message}")

            quarantine_record = QuarantineEnvelope(
                raw_payload=raw_message,
                failure_reasons=errors,
                violation_timestamp=datetime.now(timezone.utc).isoformat(),
                producer_service=self.producer_name,
                contract_target=self.contract_name
            )
            return False, None, quarantine_record

        return True, parsed_json, None

# 3. Execution Pipeline Simulation
def execute_pipeline_mock():
    enforcer = DataContractEnforcementEngine(
        contract_schema=ORDER_CONTRACT_SPEC, 
        producer_name="checkout-service"
    )

    incoming_traffic = [
        # 1. Payload Valid
        json.dumps({
            "order_id": "ORD-12345678",
            "account_id": "a98a13a8-466d-4767-827c-3f269a84497e",
            "order_timestamp": "2024-03-30T10:15:30Z",
            "total_amount": 150000.0,
            "items_count": 3,
            "payment_status": "SETTLED"
        }),
        # 2. Payload Pelanggaran Semantik (total_amount < 1000 & invalid enum)
        json.dumps({
            "order_id": "ORD-87654321",
            "account_id": "b28a13a8-466d-4767-827c-3f269a84497f",
            "order_timestamp": "2024-03-30T10:16:00Z",
            "total_amount": 500.0, # Minimum 1000
            "items_count": 0,      # Minimum 1
            "payment_status": "UNKNOWN_VAL" # Enum violation
        }),
        # 3. Payload Breaking Change (Ada field liar dan id regex cacat)
        json.dumps({
            "order_id": "MALFORMED-ORD",
            "account_id": "c38a13a8-466d-4767-827c-3f269a844970",
            "order_timestamp": "2024-03-30T10:17:00Z",
            "total_amount": 25000.0,
            "items_count": 2,
            "payment_status": "PENDING",
            "unauthorized_field": "infiltrating_lakehouse" # Breaking schema
        }),
        # 4. Payload Rusak Secara Sintaksis (Truncated JSON)
        '{"order_id": "ORD-99999999", "account_id": "broken...'
    ]

    clean_sink: List[Dict[str, Any]] = []
    quarantine_sink: List[Dict[str, Any]] = []

    for msg in incoming_traffic:
        is_valid, valid_data, quarantine_data = enforcer.validate_and_route(msg)
        if is_valid:
            logger.info(f"CONTRACT PASSED: Order ID {valid_data['order_id']} dialirkan ke Bronze Storage.")
            clean_sink.append(valid_data)
        else:
            logger.error(f"CIRCUIT BREAKER TRIGGERED: Melakukan isolasi ke Quarantine Sink!")
            logger.error(f"Penyebab Kegagalan: {quarantine_data.failure_reasons}")
            quarantine_sink.append(asdict(quarantine_data))

    print(f"\nRingkasan Eksekusi:")
    print(f"Data Sukses ke Lakehouse: {len(clean_sink)} record.")
    print(f"Data Diisolasi ke Karantina: {len(quarantine_sink)} record.")

if __name__ == "__main__":
    execute_pipeline_mock()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus Nyata: Kasus *Core Payment Data Drift* di Perusahaan FinTech Tier-1
* **Latar Belakang:** FinTech melayani 60 juta transaksi per hari. Data transaksi dialirkan dari service Core Banking ke Kafka, lalu diproses via Apache Spark Streaming menuju Delta Lake untuk deteksi *Real-Time Fraud Prevention* dan perhitungan saldo buku besar (*general ledger*).
* **Insiden:** Tim Core Banking merilis *patch* mikroservis yang mendepresiasi *field* `merchant_tax_id` dan menggantinya dengan objek *nested* `tax_attributes: { tax_id: str, country_code: str }`. Tidak ada *data contract* yang disepakati.
* **Dampak:** Spark Streaming gagal mem-parsing skema (*DeserException*), memicu *restart loop* berulang kali selama 4 jam. *Pipeline latency* meledak dari 3 detik menjadi 240 menit. Sistem Fraud Detection lumpuh (*blind spot*), meloloskan fraud transaksi senilai milyaran rupiah, dan pelaporan keuangan regulator tertunda.
* **Solusi Arsitektur Modern:**
  1. Penerapan **Open Data Contract Standard (ODCS)** pada repositori microservice. Gitlab CI/CD mengintegrasikan *Schema Compatibility Validator* dengan Confluent Schema Registry dalam mode `FULL_TRANSITIVE`.
  2. Implementasi **Two-Phase Enforcement**:
     - *Phase 1:* Jika skema diubah secara inkompatibel, *PR pipeline* di-reject otomatis di repo Microservice.
     - *Phase 2:* Pada runtime Spark, pipeline menggunakan *Circuit Breaker Quarantine Engine*. Pesan yang melanggar kontrak dialirkan secara asinkron ke S3 `s3://payment-lake-quarantine/errors/` tanpa menghentikan *streaming consumer* dari pesan valid lainnya.
* **Hasil:** Eliminasi insiden *pipeline downtime* hingga 0 jam (*zero-disruption*), identifikasi *breaking change* 100% terdeteksi di level PR produsen, dan penanganan data anomali berkurang dari hitungan hari menjadi hitungan menit via *reprocessing dead-letter*.

---

### 9. Trade-offs

| Aspek Arsitektur | In-Line Enforcement (Strict) | Asynchronous Quarantine | Permissive Ingestion (Post-hoc dbt tests) |
| :--- | :--- | :--- | :--- |
| **Latensi Pipeline** | Bertambah (overhead komputasi serialisasi + regex validasi ~2-5 ms/event). | Sangat Rendah (routing paralel via background thread pool). | Nol pada level ingestion; tinggi di level analytical batch. |
| **Throughput (EPS)** | Sedang (~20,000 - 50,000 ops/sec per worker node). | Tinggi (> 150,000 ops/sec per worker node). | Maksimal (hanya write stream langsung ke storage). |
| **Integritas Data** | Mutlak (Zero poisoned data pada downstream analytics). | Terkendali (Data kotor terisolasi seketika). | Rentan (Data kotor mencemari data warehouse sebelum dicek). |
| **Biaya Komputasi** | Tinggi di CPU producer/ingestion broker. | Moderat (Storage DLQ bertambah). | Rendah di ingestion, sangat mahal di DW compute saat reprocessing. |
| **Kompleksitas Ops** | Tinggi (Memerlukan tooling registry, linting CI/CD, alert triaging). | Menengah-Tinggi (Perlu DLQ consumer dan reconciler). | Rendah di awal, bencana di skala besar (*tech debt* tinggi). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Anti-Patterns):
1. **Validasi Skema Tanpa Rule Semantik:** Mengira bahwa validasi tipe data saja (tipe `float`) sudah cukup, padahal nilai `amount: -999999.0` secara skema lolos namun merusak semantik analitik finansial.
2. **Synchronous Exception Termination:** Melempar `sys.exit()` atau `raise Exception` pada consumer stream worker saat satu data gagal validasi. Hal ini membunuh consumer group dan memicu *Kafka consumer rebalance storm*.
3. **Mengabaikan Backward Compatibility Mode:** Menyetel Schema Registry ke mode `NONE`. Begitu produsen menghapus field tanpa default value, downstream Spark reader akan crash seketika.
4. **Quarantine Storage Tanpa TTL & Replay Mechanism:** Mengalirkan data rusak ke bucket karantina dan membiarkannya terlupakan tanpa mekanisme alerting, retention policy, atau *event replay tooling*.

#### Panduan Troubleshooting Produksi:
* **Gejala:** Latensi consumer stream Kafka melonjak tajam setelah contract validator aktif.
  * *Investigasi:* Periksa implementasi engine regex atau ukuran payload JSON yang sangat masif (*payload bloating*). JSONSchema dengan regular expression kompleks bersifat *CPU-bound*.
  * *Solusi:* Cache compiled JSON validator instance (`Draft202012Validator`) secara statis di memory worker; jangan inisialisasi ulang validator pada setiap iterasi record event.
* **Gejala:** PagerDuty banjir notifikasi *false-positive* DLQ.
  * *Investigasi:* Produsen data menambahkan *optional field* baru, namun kontrak disetel dengan `"additionalProperties": False`.
  * *Solusi:* Evaluasi toleransi evolusi skema. Jika field baru tidak melanggar tipe yang ada, gunakan version bump semver *minor* dan update contract artifact di registry.

---

### 11. Best Practices (Production Checklist)

- [ ] **Contract Versioning:** Gunakan SemVer eksplisit (`Major.Minor.Patch`) pada seluruh artefak kontrak.
  - `Patch`: Perubahan deskripsi metadata, penambahan test assertions non-blocking.
  - `Minor`: Penambahan *optional field* dengan nilai default (backward compatible).
  - `Major`: Penghapusan field, modifikasi tipe field, penambahan constraint validasi ketat.
- [ ] **Schema Registry Locking:** Konfigurasikan Schema Registry pada mode minimal `BACKWARD_TRANSITIVE` atau `FULL`.
- [ ] **Fail-Safe Quarantine Pattern:** Pastikan setiap record yang dibuang ke DLQ menyertakan `envelope` audit:
  - Header data asli (`raw_payload`)
  - Pesan error validasi spesifik
  - Timestamp kegagalan
  - Nama identitas produsen (*producer_id*)
- [ ] **Pre-Commit Linting:** Pasang *pre-commit git hooks* dan *CI workflow* di repositori produsen untuk mengeksekusi validasi kontrak secara otomatis sebelum merge ke `main`.
- [ ] **Stateless Stream Enforcers:** Buat komponen validasi *idempotent* dan *stateless* agar dapat di-scale secara horizontal di container cluster (Kubernetes/EKS).

---

### 12. Hands-on Practice

Dalam praktikum ini, Anda akan membangun sistem *Shift-Left CI/CD Linting* lokal dan *In-Line Contract Testing Engine*.

#### Persiapan File Structure
Siapkan struktur direktori pada workstation Anda:
```bash
mkdir -p hands-on/m02/contracts
mkdir -p hands-on/m02/src
mkdir -p hands-on/m02/data
mkdir -p hands-on/m02/tests
cd hands-on/m02
```

#### Langkah 1: Buat Data Contract Definition
Simpan file berikut di `hands-on/m02/contracts/user_signups_contract.yaml`:

```yaml
contract_id: "urn:datacontract:checkout:user_signups"
version: "1.2.0"
owner: "identity-team@enterprise.com"
status: "ACTIVE"

schema:
  type: "object"
  properties:
    user_id:
      type: "string"
      format: "uuid"
    username:
      type: "string"
      minLength: 5
      maxLength: 30
    email:
      type: "string"
      format: "email"
    age:
      type: "integer"
      minimum: 18
      maximum: 120
    is_active:
      type: "boolean"
  required:
    - "user_id"
    - "username"
    - "email"
    - "age"
    - "is_active"
  additionalProperties: false

sla:
  latency_seconds: 5
  freshness_hours: 1
```

#### Langkah 2: Buat Pipeline Contract Enforcement Engine
Simpan file berikut di `hands-on/m02/src/pipeline_enforcer.py`:

```python
import json
import yaml
import sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

class ProductionContractEnforcer:
    def __init__(self, contract_path: str):
        with open(contract_path, "r") as f:
            self.contract_def = yaml.safe_load(f)
            
        self.schema = self.contract_def["schema"]
        # FormatChecker penting untuk format: uuid, email, date-time
        self.validator = Draft202012Validator(self.schema, format_checker=FormatChecker())

    def validate_record(self, record: dict) -> tuple[bool, list[str]]:
        errors = []
        for error in self.validator.iter_errors(record):
            field = ".".join([str(p) for p in error.path]) if error.path else "root"
            errors.append(f"[{field}] {error.message}")
        return len(errors) == 0, errors

    def process_batch(self, batch_file_path: str):
        passed_records = []
        quarantine_records = []

        with open(batch_file_path, "r") as f:
            events = json.load(f)

        for idx, event in enumerate(events):
            is_valid, errors = self.validate_record(event)
            if is_valid:
                passed_records.append(event)
            else:
                quarantine_records.append({
                    "record_index": idx,
                    "payload": event,
                    "errors": errors
                })

        return passed_records, quarantine_records

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Penggunaan: python pipeline_enforcer.py <path_contract> <path_batch_data>")
        sys.exit(1)

    enforcer = ProductionContractEnforcer(sys.argv[1])
    clean, poisoned = enforcer.process_batch(sys.argv[2])
    
    print(f"=== HASIL VALIDASI DATA CONTRACT ===")
    print(f"Total Record: {len(clean) + len(poisoned)}")
    print(f"Data Clean (Valid): {len(clean)}")
    print(f"Data Quarantine (Broken): {len(poisoned)}")
    
    if poisoned:
        print("\nDetail Pelanggaran Data Karantina:")
        print(json.dumps(poisoned, indent=2))
```

#### Langkah 3: Buat Mock Data Input
Simpan file berikut di `hands-on/m02/data/input_stream.json`:

```json
[
  {
    "user_id": "7bf3b379-2425-4b14-8f0a-709ecbdcae60",
    "username": "budi_santoso",
    "email": "budi.santoso@enterprise.com",
    "age": 28,
    "is_active": true
  },
  {
    "user_id": "b3e0c06a-a820-43db-bc4a-9eef2771d9bc",
    "username": "adi",
    "email": "adi_invalid_email",
    "age": 16,
    "is_active": true
  },
  {
    "user_id": "non-uuid-string-identifier",
    "username": "dewi_lestari",
    "email": "dewi.lestari@enterprise.com",
    "age": 34,
    "is_active": true,
    "unauthorized_attribute": "injected_data"
  }
]
```

#### Langkah 4: Eksekusi Praktikum
Jalankan dependensi dan eksekusi skrip:

```bash
pip install jsonschema pyyaml rfc3987 fqdn isoduration email-validator
python hands-on/m02/src/pipeline_enforcer.py hands-on/m02/contracts/user_signups_contract.yaml hands-on/m02/data/input_stream.json
```

**Ekspektasi Output:**
```
=== HASIL VALIDASI DATA CONTRACT ===
Total Record: 3
Data Clean (Valid): 1
Data Quarantine (Broken): 2

Detail Pelanggaran Data Karantina:
[
  {
    "record_index": 1,
    "payload": {
      "user_id": "b3e0c06a-a820-43db-bc4a-9eef2771d9bc",
      "username": "adi",
      "email": "adi_invalid_email",
      "age": 16,
      "is_active": true
    },
    "errors": [
      "[username] 'adi' is too short",
      "[email] 'adi_invalid_email' is not a 'email'",
      "[age] 16 is less than the minimum of 18"
    ]
  },
  {
    "record_index": 2,
    "payload": {
      "user_id": "non-uuid-string-identifier",
      "username": "dewi_lestari",
      "email": "dewi.lestari@enterprise.com",
      "age": 34,
      "is_active": true,
      "unauthorized_attribute": "injected_data"
    },
    "errors": [
      "[root] Additional properties are not allowed ('unauthorized_attribute' was unexpected)",
      "[user_id] 'non-uuid-string-identifier' is not a 'uuid'"
    ]
  }
]
```

---

### 13. Exercise

#### Level Easy
Buat skrip verifikasi statis (`contracts/linter.py`) yang memvalidasi bahwa setiap file YAML kontrak dalam folder `contracts/` memuat blok wajib: `contract_id`, `version`, `owner`, dan `schema`. Skrip mengembalikan status *exit code 1* jika ada atribut wajib yang absen.

#### Level Medium
Kembangkan skrip validator pada praktikum (`pipeline_enforcer.py`) agar dapat mengekspor data yang masuk ke keranjang karantina (`quarantine_records`) secara otomatis menjadi file partisi berformat JSON-Lines di direktori `hands-on/m02/quarantine/year=YYYY/month=MM/quarantine_events.jsonl` dengan injeksi metadata audit (`failed_at`, `contract_version`).

#### Level Hard
Rancang modul Python yang membandingkan dua file skema kontrak (`contract_v1.yaml` dan `contract_v2.yaml`) dan mendeteksi apakah perubahan skema bersifat **BREAKING** atau **NON-BREAKING** secara otomatis.
- **Kategori Breaking:** Penghapusan field lama, penambahan constraint `required`, pengetatan `minLength` atau `minimum`, modifikasi tipe tipe data primitive.
- **Kategori Non-Breaking:** Penambahan field baru dengan status *optional* (*not in required list*), relaksasi constraint `maximum`.
Program harus melempar `SchemaBreakingException` jika mendeteksi pelanggaran breaking change tanpa kenaikan SemVer Major.

---

### 14. Challenge

**Skenario Kasus:**
Sebuah sistem perbankan terdistribusi memiliki microservice mutasi rekening legacy yang memancarkan data polymorphik berkecepatan 30.000 event/detik ke Apache Kafka. Masalahnya:
1. Skema event berubah-ubah tergantung jenis mutasi: `TRANSFER`, `WITHDRAWAL`, `BILL_PAYMENT`, `FEE_INTEREST`.
2. Beberapa payload legacy memiliki struktur anomali berupa serialisasi *string-encoded JSON* ganda (double-escaped JSON string).
3. Konsumen analitik hilir menuntut validasi SLA ketat: Setiap event tidak boleh memiliki latensi pemrosesan in-line lebih dari 10 milidetik, namun event yang melanggar kontrak tidak boleh menghilangkan audit trail finansial.

**Tugas Arsitektur Anda:**
Rancang dan buat prototipe sistem *Polymorphic Contract Router & Zero-Drop Sanitizer* menggunakan Python:
- Mampu mendeteksi secara dinamis kontrak spesifik yang harus diterapkan berdasarkan *field discriminator* (`event_type`).
- Mengimplementasikan *Auto-Healing Pre-processor* untuk membersihkan double-escaped JSON sebelum contract validation dieksekusi.
- Menyediakan *Quarantine Circuit Breaker* dengan zero data drop dan *fallback asynchronous buffer* jika terjadi lonjakan payload anomali mendadak.
- Siapkan laporan analisis performa throughput dan overhead latensi (CPU time per validation).

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Apa perbedaan mendasar antara Data Testing tradisional (misal: pengujian dbt test di data warehouse) dengan Shift-Left Data Quality?**
   - *Jawaban:* Data testing tradisional bersifat pasif dan reaktif (post-hoc) yang dieksekusi setelah data masuk ke penyimpanan analitik, sehingga data cacat sudah mencemari sistem. Shift-Left memindahkan validasi ke level hulu (CI/CD microservice dan in-line producer ingestion) untuk membendung data cacat sebelum mendarat di storage permanen.
2. **Mengapa aturan `"additionalProperties": false` sangat kritikal dalam spesifikasi skema Data Contract berbasis JSON Schema?**
   - *Jawaban:* Aturan ini mencegah producer menyuntikkan kolom liar (*undocumented fields*) tanpa izin, melindungi downstream storage dari *schema bloat* tak terkelola dan kegagalan deserialisasi tabel.
3. **Sebutkan minimal 3 atribut meta wajib yang harus dicantumkan pada sebuah Data Contract standar enterprise!**
   - *Jawaban:* `contract_id` (pengenal unik), `version` (SemVer skema), `owner` (identitas tim pemilik/penanggung jawab domain data), dan `schema` (definisi tipe dan batasan teknis field).
4. **Apa implikasi dari perubahan skema bertipe BACKWARD Compatibility pada Apache Kafka / Schema Registry?**
   - *Jawaban:* Konsumen dengan skema baru dapat membaca data yang diproduksi dengan skema lama. Artinya, produsen dapat menambahkan field baru selama field tersebut bersifat opsional atau memiliki default value.
5. **Apa fungsi utama dari komponen Dead Letter Queue (DLQ) / Quarantine Table dalam arsitektur data?**
   - *Jawaban:* Mengisolasi event yang gagal tervalidasi atau rusak secara struktural/semantik agar tidak menghentikan arus aliran (*pipeline halt*) event valid lainnya, sekaligus mempertahankan jejak audit untuk investigasi dan reprocessing.

#### Intermediate (5 Soal)
1. **Bagaimana cara mendeteksi Semantic Drift yang tidak memicu Schema Deserialization Error?**
   - *Jawaban:* Menggunakan assertions validasi bisnis (*business rules*) di level in-line contract engine atau checkpoint testing framework (Great Expectations), seperti batasan numerik (`minimum`, `maximum`), validasi format regex, pengecekan dependensi silang antar-kolom, atau validasi nilai enum.
2. **Mengapa deserialisasi JSONSchema dengan library standar Python bisa menjadi bottleneck pada streaming ingestion berkecepatan tinggi, dan bagaimana solusinya?**
   - *Jawaban:* Penyebabnya adalah kompilasi ulang JSON Schema dan evaluasi ekspresi regex kompleks di setiap iterasi record payload yang memakan siklus CPU. Solusinya: Meng-cache skema objek kompilasi validator, menggunakan validator biner berkinerja tinggi (seperti `fastjsonschema` / Rust-based Python bindings), atau bermigrasi ke skema serialisasi biner seperti Apache Avro / Protobuf.
3. **Apa perbedaan antara mode Schema Registry `FULL` dan `FULL_TRANSITIVE`?**
   - *Jawaban:* `FULL` hanya menjamin kompatibilitas maju dan mundur antara versi *n* dan versi *n-1* (satu versi sebelumnya). `FULL_TRANSITIVE` menjamin kompatibilitas maju dan mundur antara skema baru dengan *seluruh* versi skema sebelumnya yang pernah diregistrasikan.
4. **Pada skenario apa Circuit Breaker harus mengambil tindakan *Hard-Fail* (menghentikan pipeline) daripada sekadar membelokkan data ke Quarantine Table?**
   - *Jawaban:* Ketika persentase data yang dialirkan ke Karantina melampaui ambang batas toleransi kegagalan sistem (misal: rasio kegagalan validasi > 20% dalam rentang waktu 5 menit), yang mengindikasikan adanya kerusakan masif pada sistem hulu atau serangan integritas, sehingga menghentikan konsumsi lebih aman daripada membanjiri ruang penyimpanan karantina.
5. **Bagaimana arsitektur Shift-Left mendukung implementasi arsitektur Data Mesh?**
   - *Jawaban:* Shift-Left memberikan kepemilikan data (*data ownership*) secara eksplisit kepada tim domain produk hulu. Dengan menyepakati Data Contract sebagai *API produk*, tim domain bertanggung jawab merilis data berkualitas tinggi sebagai artefak produk, menghilangkan beban tim data terpusat sebagai penambal error.

#### Skenario Kasus Produksi (3 Soal)
1. **Skenario 1:** Tim Ingestion Anda mendapati bahwa 15% dari total record harian masuk ke folder Karantina karena perubahan format timestamp dari ISO8601 (`2024-03-30T10:00:00Z`) menjadi format Epoch Unix Millisecond (`1711792800000`) oleh tim Backend. Downstream dashboard kehilangan data signifikan. Apa langkah mitigasi terstruktur Anda?
   - *Jawaban:* 
     1. Komunikasikan segera insiden ke Tim Backend pemilik domain untuk mengembalikan format atau menghentikan rilis patch bermasalah.
     2. Lakukan evaluasi cepat pada contract definitions: update kontrak dengan SemVer Minor untuk mendukung type union (menerima ISO8601 string ATAU integer epoch) guna memulihkan pipeline sementara.
     3. Tulis batch reprocessing script untuk membaca payload dari folder karantina, mentransformasikan format epoch ke format standar, lalu me-replay (*re-inject*) data tersebut ke Bronze/Silver Ingestion topic.
     4. Terapkan blocking CI linting di repo tim Backend agar kejadian perubahan format tipe data primitif tidak terulang di masa depan.
2. **Skenario 2:** Anda merancang pipeline streaming ingestion transaksi kripto dengan beban 80.000 event per detik. Pipeline menggunakan validasi skema runtime yang menyebabkan konsumsi CPU worker mencapai 100% dan memicu penumpukan Kafka Consumer Lag. Bagaimana Anda merekayasa ulang arsitektur validasi tersebut?
   - *Jawaban:*
     1. Ganti skema serialisasi teks JSON runtime menjadi skema binary terkompilasi menggunakan Confluent Avro atau Protobuf di tingkat produsen, sehingga validasi tipe data dikerjakan pada fase kompilasi biner serialization di memori produsen tanpa overhead regex JSON di worker.
     2. Terapkan strategi validasi bertingkat: Lakukan *Structural validation* ketat via schema ID biner di event broker, dan offload validasi semantik yang rumit ke micro-batch window (misal: Apache Spark Micro-batching atau Flink interval) alih-alih validasi record-by-record di event listener tunggal.
     3. Scale-out consumer partition dan node worker secara horizontal untuk mendistribusikan beban komputasi evaluasi kontrak.
3. **Skenario 3:** Tim Data Science mengeluhkan bahwa model prediksi churn mereka di Gold Layer mengalami penurunan akurasi drastis (*model drift*). Saat diaudit, skema tabel tidak rusak sama sekali (tidak ada error di pipeline), namun nilai kolom `session_duration_minutes` berubah dari menit menjadi detik sejak dua minggu lalu. Mengapa hal ini bisa lolos dan bagaimana contract architecture mencegahnya?
   - *Jawaban:*
     - *Penyebab Lolos:* Pipeline hanya memvalidasi tipe fisik (*structural validation*: field bertipe numerik/float tetap bernilai numerik), namun kehilangan lapisan *semantic testing* dan *distribution constraint enforcement*.
     - *Pencegahan:* 
       1. Perluas Data Contract dengan batasan range semantik (`minimum`, `maximum`) dan unit metrik eksplisit pada ODCS.
       2. Terapkan integrasi automated data quality testing via Great Expectations / Soda Core di pipeline orchestration (misal: dbt-expectations) yang memverifikasi stabilitas distribusi statistik, seperti `expect_column_mean_to_be_between` atau `expect_column_quantile_values_to_be_between`.
       3. Buat automated statistical circuit breaker yang mendeteksi perubahan mean/median distribusi data secara signifikan antarbundel ingestion sebelum dipromosikan ke Silver/Gold Layer.

---

### 16. Summary

Implementasi **Shift-Left Data Quality dan Data Contract Enforcement** merepresentasikan pergeseran paradigma dari manajemen data reaktif ke pertahanan kualitas data proaktif. 

Tiga pilar fundamental yang dipelajari pada modul ini:
1. **Contract-as-Code:** Data Contract adalah kontrak hukum teknis antara tim domain produsen dan konsumen, didefinisikan secara deklaratif, terikat *versioning* (SemVer), dan diverifikasi sejak level Pull Request via CI/CD pipelines.
2. **In-Line Verification & Circuit Breaking:** Mencegah kontaminasi *lakehouse* dengan membendung anomali data di gerbang masuk (*ingestion gateway*). Alih-alih merusak seluruh pipeline pemrosesan, data non-konformatif diisolasi ke dalam *Quarantine Storage* / DLQ secara asinkron lengkap beserta konteks audit trail.
3. **Semantic Integrity Beyond Schema:** Validasi skema tipe biner/data hanyalah langkah dasar. Perlindungan sejati dari *silent data corruption* memerlukan pengujian semantik bisnis (*value bounds, formatting regex, business assertions, and distribution monitoring*) yang dijalankan sedekat mungkin dengan sumber transaksi.