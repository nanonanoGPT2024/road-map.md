# Bab 09: Shift-Left Data Quality Testing & Contract Enforcement
## Modul 01: Fondasi Shift-Left Data Quality, Declarative Contracts, dan Ingestion Gateways

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang dan Mengimplementasikan** *Declarative Data Contract* menggunakan spesifikasi berbasis skema (JSON Schema / YAML ODCS - *Open Data Contract Standard*) untuk downstream consumer tingkat lanjut (LLM pipelines, Feature Stores, Autonomous Agent memory).
- **Membangun** pipeline pengujian *Shift-Left* pada siklus CI/CD producer untuk memvalidasi perubahan skema sebelum kode produsen di-deploy ke production.
- **Mengembangkan** *Inline Validation Gateway* dan *Circuit Breaker* pada layer ingestion streaming/batch dengan *zero-data-loss dead-letter queue (DLQ)* architecture.
- **Mengevaluasi dan Menerapkan** aturan kompatibilitas skema (*BACKWARD*, *FORWARD*, *FULL*) secara programatik untuk mencegah *breaking changes* pada data downstream.
- **Mengintegrasikan** metrik *observability* kualitas data berbasis *Semantic SLA/SLO* ke dalam platform monitoring enterprise (Prometheus/OpenTelemetry).

---

### 2. Concept Overview (Mental Model & Teori Inti)

#### Paradigma Tradisional: Shift-Right Data Quality
Secara historis, data engineering beroperasi di bawah paradigma *Shift-Right*. Produsen data (aplikasi *microservices*, database operasional) mengubah skema atau logika bisnis tanpa koordinasi. Data yang kotor (*corrupted*, inkonsisten, *null-violated*) terlanjur masuk ke *Data Lake* atau *Lakehouse*. Data Engineer kemudian bertanggung jawab menulis pipeline pembersih (menggunakan dbt, Great Expectations, atau custom PySpark jobs) jauh di hilir (*downstream*). 

**Konsekuensi Negatif:**
- Tim data terus-menerus memadamkan api (*data firefighting*).
- Downtime pada dashboard analytics.
- Model Machine Learning dan Autonomous AI Agents menyerap data halusinatif atau mengalami *drift crash*.

```
Shift-Right (Antipattern):
[App/DB] ---> [Event/CDC] ---> [Lakehouse/Storage] ---> [dbt Test / Spark DQ] ---> [CRASH: Downstream AI/ML]
                                                           ^
                                                           | Data rusak terlanjur masuk
```

#### Paradigma Baru: Shift-Left Data Quality & Data Contracts
*Shift-Left Data Quality* memindahkan tanggung jawab integritas dan semantik data sedekat mungkin ke sumber (*upstream producer*). 

Sebuah **Data Contract** adalah perjanjian formal dan mengikat antara produsen data (*software engineering teams*) dan konsumen data (*data engineers, ML scientists, AI engineers*). Kontrak ini tidak hanya mendefinisikan tipe data (*syntax*), tetapi juga batasan nilai (*semantics*), metadata tata kelola (*governance*), frekuensi/latensi, dan *Service Level Objectives* (SLO).

```
Shift-Left (Modern Architecture):
[App Code] ---> [CI/CD Schema Check] ---> [Inline Gateway/Contract Enforcement] ---> [Clean Data: AI Agent Store]
     |                   |                               |
     +-(PR Blocked if)---+                               +-(Violation -> DLQ & Alert)
```

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada ekosistem modern yang ditenagai oleh **Autonomous AI Agents** dan **Real-time Feature Stores**:
1. **Kegagalan Katastropik AI Agent**: AI Agent yang mengonsumsi *unstructured* atau *semi-structured schema* mengandalkan *tool-calling* berbasis format JSON deterministik. Jika tipe data kolom `account_status` bermigrasi dari `integer` (misal: `1`) menjadi `string` (misal: `"ACTIVE"`), *reasoning engine* LLM dapat memicu eksekusi *tool* yang salah atau masuk ke dalam *infinite loop hallucination*.
2. **Biaya Komputasi yang Sia-sia**: Memproses terabyte data korup di Lakehouse menggunakan kluster GPU/Spark yang mahal sebelum akhirnya membuangnya di tahap *data cleaning* downstream adalah pemborosan infrastruktur (*cloud-cost inefficiency*).
3. **Pemisahan Tanggung Jawab (*Decoupled Ownership*)**: Data Contract membebankan kepemilikan kualitas data kepada *upstream software engineer* pemilik *domain microservice*. Mereka tidak diizinkan men-deploy service jika perubahan skema mereka melanggar kontrak data yang disepakati (*breaking change*).

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur *Shift-Left Ingestion Gatekeeper* dengan dua lapis pertahanan:
1. **Lapis Statis**: Validasi CI/CD saat Pull Request producer.
2. **Lapis Dinamis**: Validasi runtime pada Streaming Ingestion Gateway.

```
                           +-------------------------------------+
                           |      Producer Git Repository        |
                           |   (Microservice Data Publisher)     |
                           +------------------+------------------+
                                              |
                                     [1] Git Push / PR
                                              v
                           +-------------------------------------+
                           |      CI/CD Pipeline Gatekeeper      |
                           |   (Runs Contract Validation Hook)   |
                           +------------------+------------------+
                                              |
                     +------------------------+------------------------+
                     | Success                                         | Schema Violation Detected
                     v                                                 v
   +------------------------------------+           +-------------------------------------+
   | Deploy Service & Register Schema   |           | Block PR & Notify Producer Engineers |
   | into Central Schema Registry       |           +-------------------------------------+
   +-----------------+------------------+
                     |
                     | [2] Emits Events (e.g. Kafka/Kinesis)
                     v
   +--------------------------------------------------------------------------------------+
   |                             Ingestion Gateway Layer                                  |
   |                                                                                      |
   |   +-------------------+          +-----------------------+     Pass      +-------+   |
   |   |   Event Payload   |  ----->  | Inline Contract Engine| ------------> | Valid |   |
   |   | (JSON / Protobuf) |          | (Pydantic / Rust Core)|               | Sink  |   |
   |   +-------------------+          +-----------+-----------+               +---+---+   |
   |                                              |                               |       |
   +----------------------------------------------|-------------------------------|-------+
                                                  | Fail                          |
                                                  v                               v
                                    +---------------------------+   +---------------------+
                                    | Dead-Letter Queue (DLQ)   |   | Iceberg Lakehouse / |
                                    | & Automated PagerDuty     |   | AI Feature Store    |
                                    +---------------------------+   +---------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Taksonomi Kompatibilitas Skema (Schema Evolution Rules)
Dalam shift-left governance, evolusi skema diklasifikasikan ke dalam 4 mode:
- **NONE**: Tidak ada pemeriksaan kompatibilitas. (Dilarang keras pada production data pipelines).
- **BACKWARD**: Konsumen dengan skema baru dapat membaca data yang diproduksi oleh skema lama. Aturan: Kolom hanya boleh dihapus jika memiliki nilai *default*, atau kolom opsional baru ditambahkan.
- **FORWARD**: Konsumen dengan skema lama dapat membaca data yang diproduksi oleh skema baru. Aturan: Kolom baru hanya boleh ditambahkan jika konsumen lama dapat mengabaikannya; penghapusan kolom dilarang.
- **FULL**: Kombinasi BACKWARD dan FORWARD. Memungkinkan produsen dan konsumen di-upgrade secara independen tanpa *downtime*.

#### B. Anatomi Data Contract
Sebuah kontrak modern mencakup:
1. **Metadata**: Nama domain, versi semantik (*SemVer*), pemilik (*owner team*), downstream impact classification (misal: Tier-1 Agent Path).
2. **Schema Definition**: Tipe data struktural, *nullability*, nested structures.
3. **Semantic Expectations**: Batasan rentang (misal: `0.0 <= confidence_score <= 1.0`), pola Regex (misal: ISO-8601 timestamps), *referential integrity markers*.
4. **Service Level Objectives (SLO)**: Target kelengkapan (*completeness*), latensi penerbitan (*freshness*), toleransi *error rate* (< 0.01%).

#### C. Mekanisme Runtime Circuit Breaking
Ketika data streaming melewati ingestion layer:
1. Setiap pesan didekodekan dan dievaluasi terhadap kontrak versi aktif.
2. Jika validasi skema atau semantik gagal, alur transaksi normal **diputus** (*circuit broken*).
3. Payload asli, metadata kegagalan (*error stack trace*, *contract version*, *timestamp*), dialihkan ke **Dead-Letter Queue (DLQ)**.
4. Metrik kegagalan diekspos ke endpoint telemetri untuk memicu sistem *pager* tim produsen.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi *Shift-Left Contract Enforcement Suite* menggunakan Python 3.11+. Sistem ini mencakup pemrosesan *Contract Schema*, validator kompatibilitas skema, serta *Inline Ingestion Gateway* yang menangani pemisahan data valid dan DLQ.

```python
"""
shift_left_contract_engine.py
Enterprise Data Contract Validation and Ingestion Gateway Module.
"""

from __future__ import annotations

import enum
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ContractEnforcementEngine")


# ---------------------------------------------------------------------------
# Domain Models & Types
# ---------------------------------------------------------------------------
class CompatibilityMode(str, enum.Enum):
    BACKWARD = "BACKWARD"
    FORWARD = "FORWARD"
    FULL = "FULL"


class SemanticRule(BaseModel):
    field: str
    rule_type: str  # e.g., 'range', 'regex', 'enum'
    parameters: Dict[str, Any]

    model_config = ConfigDict(frozen=True)


class FieldDefinition(BaseModel):
    type: str  # 'string', 'integer', 'float', 'boolean', 'datetime'
    required: bool = True
    nullable: bool = False
    description: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class DataContract(BaseModel):
    contract_id: str
    version: str  # SemVer: major.minor.patch
    dataset_name: str
    owner_team: str
    schema_definition: Dict[str, FieldDefinition]
    semantic_rules: List[SemanticRule] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class ProcessedRecord(BaseModel):
    raw_payload: Dict[str, Any]
    validated_payload: Optional[Dict[str, Any]]
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Contract Compatibility Checker (CI/CD Static Linter)
# ---------------------------------------------------------------------------
class ContractCompatibilityChecker:
    """Memverifikasi kepatuhan backward/forward antar versi Data Contract."""

    TYPE_MAPPING = {
        "string": str,
        "integer": int,
        "float": float,
        "boolean": bool,
        "datetime": datetime,
    }

    @classmethod
    def check_compatibility(
        cls,
        old_contract: DataContract,
        new_contract: DataContract,
        mode: CompatibilityMode = CompatibilityMode.BACKWARD,
    ) -> Tuple[bool, List[str]]:
        violations: List[str] = []

        old_fields = old_contract.schema_definition
        new_fields = new_contract.schema_definition

        if mode in (CompatibilityMode.BACKWARD, CompatibilityMode.FULL):
            # BACKWARD: Konsumen baru harus bisa membaca data skema lama.
            # Konsekuensi: Tidak boleh menambahkan field BARU yang bersifat REQUIRED tanpa default.
            for field_name, new_def in new_fields.items():
                if field_name not in old_fields and new_def.required and not new_def.nullable:
                    violations.append(
                        f"Backward incompatibility: Kolom baru '{field_name}' "
                        f"wajib diisi (required=True) tanpa skema default/nullable."
                    )

            # Tidak boleh mengubah tipe data field yang sudah ada secara destruktif
            for field_name, old_def in old_fields.items():
                if field_name in new_fields:
                    new_def = new_fields[field_name]
                    if old_def.type != new_def.type:
                        violations.append(
                            f"Backward incompatibility: Perubahan tipe data pada '{field_name}' "
                            f"dari {old_def.type} ke {new_def.type}."
                        )

        if mode in (CompatibilityMode.FORWARD, CompatibilityMode.FULL):
            # FORWARD: Konsumen lama harus bisa membaca data skema baru.
            # Konsekuensi: Tidak boleh menghapus field yang sebelumnya ada.
            for field_name in old_fields:
                if field_name not in new_fields:
                    violations.append(
                        f"Forward incompatibility: Kolom '{field_name}' dihapus pada versi baru."
                    )

        return (len(violations) == 0, violations)


# ---------------------------------------------------------------------------
# Dynamic Schema Generator & Gateway Validator
# ---------------------------------------------------------------------------
class IngestionGateway:
    """Dynamic gateway untuk parsing, validasi semantik, dan routing DLQ."""

    def __init__(self, contract: DataContract) -> None:
        self.contract = contract
        self._runtime_model = self._compile_pydantic_model(contract)

    def _compile_pydantic_model(self, contract: DataContract) -> type[BaseModel]:
        """Menyusun Pydantic Model secara dinamis dari definisi skema kontrak."""
        fields_dict: Dict[str, Any] = {}
        for field_name, field_def in contract.schema_definition.items():
            py_type = ContractCompatibilityChecker.TYPE_MAPPING.get(field_def.type, Any)

            if field_def.nullable:
                py_type = Optional[py_type]

            default_val = ... if field_def.required else None
            fields_dict[field_name] = (py_type, default_val)

        return create_model(
            f"DynamicContract_{contract.contract_id.replace('-', '_')}",
            **fields_dict,
            __config__=ConfigDict(extra="forbid"),  # Blokir injection undeclared fields
        )

    def _evaluate_semantics(self, payload: Dict[str, Any]) -> List[str]:
        semantic_errors: List[str] = []
        for rule in self.contract.semantic_rules:
            val = payload.get(rule.field)
            if val is None:
                continue

            if rule.rule_type == "range":
                min_val = rule.parameters.get("min")
                max_val = rule.parameters.get("max")
                if min_val is not None and val < min_val:
                    semantic_errors.append(
                        f"Field '{rule.field}' bernilai {val}, melanggar batas minimum {min_val}."
                    )
                if max_val is not None and val > max_val:
                    semantic_errors.append(
                        f"Field '{rule.field}' bernilai {val}, melanggar batas maksimum {max_val}."
                    )

            elif rule.rule_type == "enum":
                allowed = rule.parameters.get("allowed", [])
                if val not in allowed:
                    semantic_errors.append(
                        f"Field '{rule.field}' bernilai '{val}', tidak termasuk dalam {allowed}."
                    )

        return semantic_errors

    def process_event(self, raw_payload: Dict[str, Any]) -> ProcessedRecord:
        """Memvalidasi payload terhadap skema struktural dan aturan semantik."""
        errors: List[str] = []
        validated_data: Optional[Dict[str, Any]] = None

        # 1. Structural Validation (Syntactic)
        try:
            instance = self._runtime_model(**raw_payload)
            validated_data = instance.model_dump()
        except ValidationError as e:
            for err in e.errors():
                loc = " -> ".join(str(l) for l in err["loc"])
                errors.append(f"Structural error at '{loc}': {err['msg']}")

        # 2. Semantic Validation (Business Logic Boundary)
        if not errors and validated_data:
            semantic_errs = self._evaluate_semantics(validated_data)
            if semantic_errs:
                errors.extend(semantic_errs)

        is_valid = len(errors) == 0
        return ProcessedRecord(
            raw_payload=raw_payload,
            validated_payload=validated_data if is_valid else None,
            is_valid=is_valid,
            errors=errors,
        )


# ---------------------------------------------------------------------------
# Dead Letter Queue Dispatcher (Mock Enterprise Infrastructure)
# ---------------------------------------------------------------------------
class DeadLetterQueueDispatcher:
    @staticmethod
    def dispatch(record: ProcessedRecord, contract_id: str) -> None:
        dlq_envelope = {
            "contract_id": contract_id,
            "failed_payload": record.raw_payload,
            "reasons": record.errors,
            "failed_at": record.processed_at.isoformat(),
        }
        logger.error(
            "CIRCUIT BREAKER: Payload ditolak masuk ke sink downstream! Mengirim ke DLQ.\n%s",
            json.dumps(dlq_envelope, indent=2),
        )


# ---------------------------------------------------------------------------
# Verification & Execution Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Memulai Eksekusi Shift-Left Data Quality Suite...")

    # A. Definisikan Data Contract Versi 1.0.0 (Baseline)
    contract_v1 = DataContract(
        contract_id="contract-agent-txn-001",
        version="1.0.0",
        dataset_name="user_financial_transactions",
        owner_team="fraud_detection_upstream",
        schema_definition={
            "transaction_id": FieldDefinition(type="string", required=True),
            "user_id": FieldDefinition(type="string", required=True),
            "amount": FieldDefinition(type="float", required=True),
            "currency": FieldDefinition(type="string", required=True),
            "risk_score": FieldDefinition(type="float", required=True),
        },
        semantic_rules=[
            SemanticRule(field="amount", rule_type="range", parameters={"min": 0.01}),
            SemanticRule(
                field="currency", rule_type="enum", parameters={"allowed": ["IDR", "USD", "SGD"]}
            ),
            SemanticRule(
                field="risk_score", rule_type="range", parameters={"min": 0.0, "max": 1.0}
            ),
        ],
    )

    # B. Uji Static CI/CD Schema Evolution Compatibility
    logger.info(">>> Melakukan Simulasi Git CI/CD Pre-merge Contract Check...")

    # Versi 2.0.0 bermasalah: Menambahkan kolom required baru 'geo_location' (Backward Incompatible)
    contract_v2_broken = DataContract(
        contract_id="contract-agent-txn-001",
        version="2.0.0",
        dataset_name="user_financial_transactions",
        owner_team="fraud_detection_upstream",
        schema_definition={
            **contract_v1.schema_definition,
            "geo_location": FieldDefinition(type="string", required=True, nullable=False),
        },
    )

    is_compat, issues = ContractCompatibilityChecker.check_compatibility(
        contract_v1, contract_v2_broken, mode=CompatibilityMode.BACKWARD
    )
    if not is_compat:
        logger.warning(
            "CI GATE ALERT: Pull Request DITOLAK karena melanggar kompatibilitas backward:\n - %s",
            "\n - ".join(issues),
        )

    # C. Dynamic Ingestion Runtime Simulation
    logger.info(">>> Menginisialisasi Ingestion Gateway dengan Contract V1...")
    gateway = IngestionGateway(contract_v1)

    # Payload 1: Data Valid untuk Autonomous Agent Feature Store
    payload_valid = {
        "transaction_id": "tx-88392",
        "user_id": "usr-00192",
        "amount": 250000.0,
        "currency": "IDR",
        "risk_score": 0.12,
    }

    # Payload 2: Pelanggaran Semantik (amount negatif & currency ilegal)
    payload_invalid_semantics = {
        "transaction_id": "tx-88393",
        "user_id": "usr-00192",
        "amount": -50.0,
        "currency": "EUR",
        "risk_score": 0.85,
    }

    # Payload 3: Pelanggaran Struktural (Tipe data keliru & undeclared extra field)
    payload_invalid_structure = {
        "transaction_id": "tx-88394",
        "user_id": "usr-00192",
        "amount": "TIDAK_VALID",  # Seharusnya float
        "currency": "USD",
        "risk_score": 0.44,
        "injected_untracked_column": "exploit",  # Forbidden extra field
    }

    test_stream = [payload_valid, payload_invalid_semantics, payload_invalid_structure]

    for idx, raw_event in enumerate(test_stream, start=1):
        logger.info("--- Memproses Pesan Event #%d ---", idx)
        result = gateway.process_event(raw_event)
        if result.is_valid:
            logger.info(
                "PASS: Data berhasil diverifikasi kontrak! Diteruskan ke Iceberg Sink:\n%s",
                result.validated_payload,
            )
        else:
            DeadLetterQueueDispatcher.dispatch(result, contract_v1.contract_id)
```

---

### 7. Edge Cases & Failure Modes (Error Recovery, Validasi, Fallback)

1. **Undeclared Metadata Injection (*Schema Leaks*)**:
   - *Failure Mode*: Tim upstream menyisipkan field debug atau PII baru tanpa mengumumkan perubahan skema.
   - *Mitigasi*: Konfigurasi dynamic parser dengan kebijakan `extra="forbid"`. Gateway langsung merejeki data tersebut ke DLQ alih-alih meloloskannya ke storage hilir.
2. **Precision Loss pada Nilai Finansial/Tinggi**:
   - *Failure Mode*: Penggunaan tipe data `float` standar menyebabkan *floating-point arithmetic rounding errors* pada pipeline model finansial.
   - *Mitigasi*: Pada skala enterprise, definisikan field numerik moneter secara eksplisit sebagai string-encoded `Decimal` pada Data Contract untuk mencegah degradasi IEEE 754.
3. **Penyimpangan Format Waktu (*Timestamp Drift & Parsing Ambiguity*)**:
   - *Failure Mode*: Producer mengirim `epoch seconds`, namun downstream mengharapkan `ISO-8601 with Timezone offset` (`YYYY-MM-DDTHH:MM:SSZ`).
   - *Mitigasi*: Gunakan *Semantic Rule Validator* berbasis Regex ketat pada level Gateway untuk memvalidasi string kepatuhan RFC-3339 sebelum parsialisasi datetime.
4. **Throttling & Bottlenecking pada Inline Gateway**:
   - *Failure Mode*: Validasi kompleks memperlambat throughput streaming hingga menyebabkan backpressure pada Kafka cluster.
   - *Mitigasi / Fallback*: Jika engine mengalami CPU saturation > 85%, aktifkan *Selective Sampling Mode* hanya pada validasi semantik bernilai komputasi tinggi, sembari mempertahankan *Structural Syntactic Check* 100% menggunakan native compiled engine (seperti Rust `pydantic-core`).

---

### 8. Trade-offs & Alternatif Solusi

| Parameter | Shift-Left Gateway + Contracts | Kafka Schema Registry (Avro/Protobuf) | Shift-Right Tests (dbt / Great Expectations) |
| :--- | :--- | :--- | :--- |
| **Titik Penindakan** | CI/CD producer + Streaming Gateway | Layer broker/serializer data | Data Lakehouse storage pasca-ingestion |
| **Cakupan Validasi** | **Struktural & Semantik Kompleks** (Rentang, Enum, SLA) | **Struktural Saja** (Tipe data, nullability) | **Semantik Penuh** & Referential Integrity Table-wide |
| **Dampak Latensi** | Rendah - Menengah (~5-15 ms pada gateway) | Sangat Rendah (< 1 ms saat serialisasi) | Nol dampak pada jalur streaming (*asynchronous*) |
| **Blast Radius Error** | **Nol** (Data rusak dibuang ke DLQ sebelum storage) | Rendah (Gagal di tingkat producer serialisasi) | **Tinggi** (Data rusak sempat tersimpan dan terbaca) |
| **Kompleksitas Ops** | Menengah (Memerlukan kontrak governance terpusat) | Rendah-Menengah (Infrastruktur Confluent/Apicurio) | Rendah (Hanya setup job batch analitik) |

---

### 9. Best Practices & Standard Industri

1. **Contract-as-Code dalam Git Terpusat**:
   Simpan definisi Data Contract dalam repositori Git khusus (misalnya: `org-data-contracts`). Gunakan GitHub Actions / GitLab CI untuk menerbitkan artefak kontrak versi baru ke *Registry* internal.
2. **Penerapan Semantic Versioning (SemVer) pada Kontrak**:
   - **PATCH**: Perubahan deskripsi metadata, penambahan aturan SLA nondestruktif.
   - **MINOR**: Penambahan kolom baru yang nullable/memiliki default (Kompatibel mundur).
   - **MAJOR**: Penghapusan kolom, perubahan tipe data primitif, pengetatan rentang aturan semantik (Inkompatibel mundur).
3. **Producer-Alert Routing (No Data Engineer Middleware)**:
   Metrik kegagalan Gateway/DLQ harus langsung mengirim alert ke kanal Slack/PagerDuty tim *software development* yang menerbitkan service tersebut. Jangan jadikan data engineer sebagai penengah untuk data upstream yang malformed.
4. **Idempotent DLQ Replay Mechanism**:
   DLQ harus menyertakan skrip atau prosedur teruji untuk melakukan *replay* data kembali ke gateway setelah tim produsen merilis perbaikan skema atau downstream kontrak telah di-upgrade.

---

### 10. Hands-on Lab Exercise: Implementasi Circuit Breaker Testing

#### Skenario:
Anda adalah Principal Data Platform Engineer yang bertugas mengamankan *Inference Pipeline Autonomous AI Agent* anti-fraud. Anda harus mencegah masuknya event mutasi rekening yang rusak sebelum mencapai vector context memory LLM.

#### Langkah 1: Persiapan Environment
Pastikan Python 3.11+ terpasang, lalu instal dependensi yang dibutuhkan:
```bash
pip install pydantic==2.6.4 jsonschema==4.21.1
```

#### Langkah 2: Buat File Definisi Kontrak (`account_contract.json`)
Simpan file berikut sebagai representasi kontrak GitOps:
```json
{
  "contract_id": "contract-core-banking-009",
  "version": "1.0.0",
  "dataset_name": "account_balance_events",
  "owner_team": "core_banking_squad",
  "schema_definition": {
    "account_id": {"type": "string", "required": true, "nullable": false},
    "balance_after": {"type": "float", "required": true, "nullable": false},
    "event_type": {"type": "string", "required": true, "nullable": false}
  },
  "semantic_rules": [
    {
      "field": "event_type",
      "rule_type": "enum",
      "parameters": {"allowed": ["DEPOSIT", "WITHDRAWAL", "TRANSFER_ADJUSTMENT"]}
    }
  ]
}
```

#### Langkah 3: Eksekusi Skrip Integrasi Gateway
Jalankan skrip Python berikut untuk memverifikasi isolasi payload yang merusak:
```python
import json
from shift_left_contract_engine import (
    DataContract,
    DeadLetterQueueDispatcher,
    FieldDefinition,
    IngestionGateway,
    SemanticRule,
)

# Load Contract
with open("account_contract.json", "r") as f:
    raw_contract = json.load(f)

contract = DataContract(
    contract_id=raw_contract["contract_id"],
    version=raw_contract["version"],
    dataset_name=raw_contract["dataset_name"],
    owner_team=raw_contract["owner_team"],
    schema_definition={
        k: FieldDefinition(**v) for k, v in raw_contract["schema_definition"].items()
    },
    semantic_rules=[SemanticRule(**r) for r in raw_contract.get("semantic_rules", [])],
)

gateway = IngestionGateway(contract)

# Data simulasi streaming
incoming_traffic = [
    {
        "account_id": "ACC-ID-9901",
        "balance_after": 1500000.50,
        "event_type": "DEPOSIT",
    },  # Valid
    {
        "account_id": "ACC-ID-9902",
        "balance_after": 250.0,
        "event_type": "UNAUTHORIZED_OVERDRAFT_OVERRIDE",  # Melanggar semantik enum
    },
]

for packet in incoming_traffic:
    result = gateway.process_event(packet)
    if result.is_valid:
        print(f"[SUCCESS] Routed to AI Agent Engine: {result.validated_payload}")
    else:
        DeadLetterQueueDispatcher.dispatch(result, contract.contract_id)
```

#### Output yang Diharapkan:
- Event pertama lolos verifikasi dan diteruskan ke AI Agent Engine.
- Event kedua memicu pemutusan circuit breaker, ditandai dengan log `CIRCUIT BREAKER: Payload ditolak masuk ke sink downstream!` dan routing otomatis ke DLQ tanpa menghentikan sistem ingestion.