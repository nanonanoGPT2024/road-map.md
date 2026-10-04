# BAB 06: Prinsip Orkestrasi Modern & Directed Acyclic Graph (DAG)
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonseptualisasikan dan menganalisis arsitektur internal scheduler mesin orkestrasi modern (fokus pada Apache Airflow 2.x/3.x, Dagster, dan Prefect), mencakup *state machine*, siklus *parsing*, serta mekanisme *concurrency control*.
- Mengimplementasikan pola eksekusi terdistribusi tingkat lanjut menggunakan `CeleryExecutor` dan `KubernetesExecutor` dengan integrasi *autoscaling* berbasis beban antrean (*event-driven autoscaler*).
- Membangun *Dynamic DAG Generation*, *Dynamic Task Mapping* (EIP: Splitter & Aggregator), serta *Custom Deferrable Operators* berbasis `asyncio` untuk mengeliminasi pemborosan sumber daya *worker slots*.
- Merancang arsitektur persistensi XCom berskala enterprise dengan *custom remote backend* (Amazon S3/GCS/MinIO) terenkripsi guna mencegah degradasi performa dan *table bloat* pada RDBMS *metadata storage*.
- Menerapkan arsitektur orkestrasi yang sepenuhnya idempoten, *fault-tolerant*, dan mendukung *deterministic backfilling* lintas zona waktu (*timezone-aware partition processing*).
- Mengintegrasikan mekanisme observabilitas (*OpenLineage*, *Prometheus metrics*, *Structured Audit Logging*) dan strategi mitigasi insiden (*SLA misses*, *Zombie Tasks*, *Deadlock detection*).

---

### 2. Prerequisites

Peserta wajib menguasai:
- **Konsep Fondasi Orkestrasi**: Memahami DAG dasar, dependensi hulu/hilir (*upstream/downstream*), serta operator bawaan standar (BashOperator, PythonOperator).
- **Pemrograman Python Tingkat Lanjut**: Penguasaan `asyncio`, *metaclass*, generator, *decorator*, penanganan *multithreading/multiprocessing*, dan serialisasi data (`pickle`, `json`, `protobuf`).
- **Infrastruktur Terdistribusi & Kontainer**: Arsitektur Kubernetes (*Pods*, *Deployments*, *StatefulSets*, *PV/PVC*, *Resource Quotas*, *KEDA*), Redis (*Pub/Sub*, antrean *broker*), dan jaringan terdistribusi.
- **Basis Data Relasional**: Pemahaman mendalam tentang PostgreSQL (MVCC, *transaction isolation level*, *row-level locking* `SELECT FOR UPDATE`, serta indeks B-Tree/GIN).
- **Pola Komputasi Data Modern**: Pemisahan tegas antara *compute plane* (Spark, Trino, Snowflake, dbt) dan *orchestration plane* (Airflow/Dagster).

---

### 3. Concept & Internal Architecture (Mendalam)

Mesin orkestrasi modern bukan sekadar *distributed cron*. Mesin ini merupakan *deterministic finite-state machine* (FSM) terdistribusi yang bertanggung jawab atas resolusi dependensi topologis, alokasi sumber daya komputasi, dan pemantauan status eksekusi.

```
+---------------------------------------------------------------------------------------------------+
|                                  AIRFLOW CORE ARCHITECTURE                                         |
+---------------------------------------------------------------------------------------------------+
                                    +-----------------------+
                                    |   DAG Directory       |
                                    |  (/opt/airflow/dags)  |
                                    +-----------+-----------+
                                                |
                                                v
+------------------------+          +-----------------------+          +----------------------------+
|                        |  Sync    |   DAG File Processor  | Serialize|   Metadata Database        |
|  Airflow Webserver     |<---------+   (Multi-threaded)    +--------->|   (PostgreSQL)             |
|  (UI / REST API)       |  State   |                       |  JSON/DB |  - dag / dag_run           |
+-----------+------------+          +-----------------------+          |  - task_instance           |
            |                                                          |  - xcom / job              |
            | Read Only (via DB)                                       +-------------+--------------+
            +------------------------------------------------------------------------+
                                                                                     ^
                                                                                     | Lock & Update
                                    +-----------------------+                        | Heartbeat
                                    |   Airflow Scheduler   +------------------------+
                                    |   (SchedulerJobLoop)  |
                                    +-----------+-----------+
                                                |
                         Enqueue Tasks via RPC  | (Celery / K8s API)
                                                v
            +-----------------------------------+-----------------------------------+
            |                                   |                                   |
            v                                   v                                   v
+-----------------------+           +-----------------------+           +-----------------------+
|  Celery Broker        |           |  Triggerer Daemon     |           |  Kubernetes API       |
|  (Redis / RabbitMQ)   |           |  (Asyncio Event Loop) |           |  (CoreV1Api)          |
+-----------+-----------+           +-----------+-----------+           +-----------+-----------+
            |                                   |                                   |
            v                                   v (Wake up)                         v
+-----------------------+           +-----------------------+           +-----------------------+
|  Celery Workers       |           | Deferrable Operators  |           |  Worker Pods          |
|  (Task Execution)     |           | (Yields Trigger)      |           |  (Ephemeral/Pod-per-T)|
+-----------+-----------+           +-----------------------+           +-----------+-----------+
            |                                                                       |
            +-----------------------------------+-----------------------------------+
                                                | Task Logs / Remote XCom
                                                v
                                    +-----------------------+
                                    | Object Storage        |
                                    | (S3 / GCS / MinIO)    |
                                    +-----------------------+
```

#### 3.1 Siklus Hidup DAG Parsing & DAG Serialization

Secara tradisional, *Webserver* mengevaluasi kode Python file DAG secara langsung. Hal ini menimbulkan kerentanan keamanan dan inefisiensi CPU yang masif. Dalam arsitektur modern:
1. **DAG File Processor Loop**: Berjalan di dalam proses `dag-processor` (terisolasi dari *Scheduler* utama). Loop ini memindai direktori DAG secara berkala (`min_file_process_interval`).
2. **AST Parsing & Dynamic DAG Rendering**: Python file dieksekusi dalam lingkungan sandbox parsial. Kode Python dievaluasi untuk menghasilkan struktur objek Python `DAG` dan `BaseOperator`.
3. **Serialization Engine**: Objek diubah menjadi representasi biner terenkode JSON (`SerializedDAGModel`) dan disimpan ke tabel `serialized_dag` di PostgreSQL.
4. **Decoupled Webserver**: Webserver tidak lagi membaca file disk `.py`. Webserver murni membaca blob JSON serial dari metadata DB, meniadakan injeksi kode arbitrer dan memangkas penggunaan I/O disk secara signifikan.

#### 3.2 Siklus Scheduler & Heartbeat Loop (State Machine Resolution)

Siklus Scheduler adalah *heartbeat loop* non-blocking yang mengeksekusi operasi berikut per tick:

$$\text{DAG State Transition}: \text{None} \to \text{SCHEDULED} \to \text{QUEUED} \to \text{RUNNING} \to \{\text{SUCCESS}, \text{FAILED}, \text{UP\_FOR\_RETRY}\}$$

Langkah detail pemrosesan per tick:
1. **Active DagRun Verification**: Scheduler mengambil baris pada tabel `dag_run` dengan `state='running'` menggunakan *pessimistic locking*:
   ```sql
   SELECT * FROM dag_run 
   WHERE state = 'running' 
   FOR UPDATE SKIP LOCKED;
   ```
2. **Topological Dependency Parsing**: Untuk setiap DagRun, Scheduler membangun dependensi hierarki tugas (*Upstream Graph*). Sebuah `TaskInstance` (TI) beralih ke state `SCHEDULED` jika dan hanya jika seluruh *upstream parents* memenuhi konfigurasi `trigger_rule` (misal: `all_success`, `all_done`, `none_failed`).
3. **Concurrency Slot Verification**: Scheduler mengevaluasi batasan konkurensi:
   - `max_active_runs_per_dag`
   - `max_active_tis_per_dag`
   - Ketersediaan slot pada *Pool* yang ditentukan.
4. **Enqueueing**: TI diubah menjadi state `QUEUED`. Payload eksekusi dikirim ke antrean eksekutor (*Redis Queue* untuk Celery, atau *API Request Payload* untuk Kubernetes API).

#### 3.3 Anatomi Triggerer & Deferrable Operators (Asyncio Event-Loop)

Dalam pola orkestrasi klasik, *Sensor* (misalnya `S3KeySensor` atau `HttpSensor`) memakan 1 slot worker (*thread/process*) secara terus-menerus selama berjam-jam hanya untuk menunggu berkas (*busy-waiting polling*).
- **Deferrable Operator Architecture**: Ketika operator mencapai titik tunggu, ia melepaskan worker slot dengan memanggil `self.defer(trigger=..., method_name=...)` dan memicu transisi state TI ke `DEFERRED`.
- **Triggerer Process**: Berjalan menggunakan satu *thread* `asyncio event loop` yang mampu menangani ribuan koneksi konkuren melalui *non-blocking I/O*.
- **Resume Protocol**: Ketika event eksternal terdeteksi oleh *Triggerer*, sinyal dikirim ke database untuk mengubah state TI kembali menjadi `SCHEDULED`, dan *Scheduler* menjadwalkan ulang eksekusi tugas pada metode callback (`method_name`) di antrean worker.

---

### 4. Why & What

| Dimensi | Pola Orkestrasi Tradisional (Monolitik/Cron) | Orkestrasi Modern Terdistribusi (Enterprise DAG) |
| :--- | :--- | :--- |
| **Kopling Komputasi** | Terikat erat (*Tight coupling*). Kode orkestrasi dan transformasi data berjalan di mesin yang sama. | Terpisah (*Decoupled*). Orkestrator murni bertindak sebagai *stateful coordinator*, komputasi didelegasikan ke engine eksternal. |
| **Pemanfaatan Sumber Daya** | Sangat boros (*Resource lock*). Sensor memblokir CPU/RAM worker secara terus-menerus. | Sangat hemat (*Resource-efficient*). Menggunakan *Deferrable Triggers* berbasis I/O asinkron. |
| **Idempotensi & Pemulihan** | Sulit dijamin. *Re-run* berisiko menduplikasi data atau merusak state sistem. | *Built-in determinism*. Partisi waktu terisolasi, atomic transactions, dan *stateless execution*. |
| **Penskalaan Eksekusi** | Terbatas pada kapasitas vertikal satu simpul VM (*Vertical Scale*). | Penskalaan horizontal dinamis via kontainerisasi (*Kubernetes Pod autoscaling* / KEDA). |
| **Manajemen State Data** | Tidak mengenal konteks data (*Data-unaware*). Hanya memantau exit status kode (0 atau non-0). | Berorientasi pada aset (*Data-aware / Asset-based*). Eksekusi dipicu oleh mutasi status partisi data. |

---

### 5. How (Workflow Detail)

Alur eksekusi tugas enterprise dari inisiasi hingga finalisasi status:

```
[DAG File Processor] -> Mengompilasi DAG & Ekstrak Dependencies
       |
       v
[Serialized DAG DB]  -> Menyimpan AST terenkode JSON ke metadata store
       |
       v
[Airflow Scheduler]  -> Mengevaluasi Jadwal & Trigger Rules -> Set TI: SCHEDULED
       |
       v
[Capacity Checker]   -> Memeriksa Pool, Concurrency, Quota -> Set TI: QUEUED
       |
       v
[Executor Mechanism] -> Celery Broker (Redis) ATAU K8s API
       |
       +-----------------------+-----------------------+
       | (CeleryExecutor)                              | (KubernetesExecutor)
       v                                               v
[Celery Worker Slot]                           [Kube-API spawn Pod]
       |                                               |
       +-----------------------+-----------------------+
                               |
                               v
                       [Worker Execution]
                               |
            +------------------+------------------+
            | (Standard Sync)                     | (Deferrable Async)
            v                                     v
   [Jalankan execute()]                  [Panggil self.defer()]
            |                                     |
            |                                     v
            |                         [Triggerer Async Loop]
            |                                     | (Event terdeteksi)
            |                                     v
            |                         [Worker resume callback]
            |                                     |
            +------------------+------------------+
                               |
                               v
                  [Remote XCom Push (S3/GCS)]
                               |
                               v
                  [Set State: SUCCESS di DB]
                               |
                               v
                  [Trigger Downstream Tasks]
```

1. **DAG Parsing**: DAG dimuat dan divalidasi keamanannya; dependensi didaftarkan ke PostgreSQL.
2. **DagRun Creation**: Triger jadwal (*Cron/Data Asset Mutation*) memicu pembuatan entri `dag_run` baru dengan `execution_date` deterministik.
3. **Task Resolution**: `SchedulerJobLoop` memeriksa ketersediaan dependensi hulu. Jika terpenuhi, TI masuk status `SCHEDULED` lalu `QUEUED`.
4. **Dispatching**:
   - Jika menggunakan `CeleryExecutor`: ID tugas dikirim ke antrean Redis/RabbitMQ. *Celery Worker* mengambil payload dari antrean.
   - Jika menggunakan `KubernetesExecutor`: Scheduler memanggil Kubernetes API Server untuk membuat *ephemeral worker pod* berbasis spesifikasi PodTemplate.
5. **Execution & State Yielding**:
   - Worker menginstansiasi operator. Jika operasi membutuhkan waktu tunggu jaringan eksternal, operator memicu `self.defer()`, melepaskan pod/worker slot, dan mendelegasikan pemantauan ke `Triggerer`.
6. **Persistence & Signal Propagation**:
   - Nilai balik tugas (*return value*) di-serialize dan dikirim langsung ke S3 melalui *Custom S3 XCom Backend*.
   - Worker mengirim heartbeat status sukses/gagal ke metadata DB.
   - Sinyal status memicu evaluasi Scheduler untuk membuka kunci eksekusi tugas-tugas hilir (*downstream*).

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual: "Menara Pengawas Bandara Internasional (Air Traffic Control)"
- **Airflow Webserver**: Layar radar dan monitor informasi jadwal penerbangan di terminal terminal penumpang. Penumpang dapat melihat status penerbangan, tetapi tidak memiliki otoritas mengarahkan pesawat.
- **DAG File Processor**: Bagian verifikasi regulasi dan manifes dokumen penerbangan yang memeriksa apakah jalur terbang bebas tabrakan secara matematis sebelum didaftarkan ke sistem.
- **Airflow Scheduler**: Petugas Pengatur Lalu Lintas Udara (Air Traffic Controller/ATC). Memantau slot landasan (*Pools*), menentukan giliran lepas landas (*Trigger Rules*), dan memberikan izin meluncur (*Queued/Running*).
- **Worker Slot (Celery/K8s)**: Landasan pacu fisik dan pesawat yang sedang membakar bahan bakar untuk bergerak.
- **Triggerer Daemon**: Area tunggu *holding pattern* di udara yang dipandu radar otomatis. Pesawat tidak memakan slot landasan pacu yang berharga; mereka menunggu sinyal radio non-blocking sebelum diperintahkan mendarat oleh ATC.
- **Custom XCom Backend**: Terminal kargo logistik terpisah untuk memindahkan kontainer bermuatan ribuan ton, bukan memasukkannya ke dalam saku petugas ATC.

```
METADATA STATE MACHINE & LOCKING
========================================================================================

+--------------------------------------------------------------------------------------+
| Scheduler Process (Thread 1)                                                         |
|                                                                                      |
| 1. BEGIN TRANSACTION;                                                                |
| 2. SELECT * FROM task_instance WHERE state='SCHEDULED' FOR UPDATE SKIP LOCKED;        |
|    |                                                                                 |
|    |--> [Lock Acquired pada TI: dag_daily_sales.ingest_orders_task]                  |
|    |                                                                                 |
| 3. Verifikasi Concurrency Limits (Pool = 'production_tier_1', Slots Max = 50)       |
| 4. UPDATE task_instance SET state='QUEUED' WHERE id=982341;                          |
| 5. COMMIT; (Lock dilepas)                                                            |
| 6. Enqueue ke Broker / K8s Client                                                    |
+--------------------------------------------------------------------------------------+
                                           |
                                           v
+--------------------------------------------------------------------------------------+
| Celery Broker (Redis Channel: default)                                               |
| Message: {"task_id": "ingest_orders_task", "dag_id": "dag_daily_sales", ...}         |
+--------------------------------------------------------------------------------------+
                                           |
                                           v
+--------------------------------------------------------------------------------------+
| Celery Worker Node (worker-node-k8s-pod-x89)                                         |
|                                                                                      |
| 1. Worker thread pop payload dari Redis                                              |
| 2. Ambil state DB -> UPDATE task_instance SET state='RUNNING', start_date=NOW();     |
| 3. Instansiasi Operator -> Inisiasi Task Execution Sandbox                          |
+--------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic Task Mapping (Airflow 2.3+)

Pola untuk memecah beban tugas (*fan-out*) secara dinamis berdasarkan data run-time, diikuti penggabungan (*fan-in*), tanpa perlu mendefinisikan jumlah tugas secara statis.

```python
from datetime import datetime
from airflow.decorators import dag, task

@dag(
    dag_id="dynamic_task_mapping_fundamental",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["core-architecture", "dynamic-mapping"]
)
def dynamic_mapping_pipeline():

    @task
    def retrieve_partition_keys() -> list[str]:
        """Menghasilkan partisi data secara deterministik saat runtime."""
        return [f"partition_year=2024/month={m:02d}" for m in range(1, 5)]

    @task
    def process_partition(partition_path: str) -> dict[str, int]:
        """Memproses partisi secara independen dalam worker slot terpisah."""
        print(f"Executing batch ingestion for: {partition_path}")
        # Simulasi penghitungan record per partisi
        simulated_records = len(partition_path) * 1000
        return {"partition": partition_path, "record_count": simulated_records}

    @task
    def aggregate_results(metrics: list[dict[str, int]]) -> int:
        """Mengonsolidasikan metrik (Fan-in / Reducer pattern)."""
        total_records = sum(entry["record_count"] for entry in metrics)
        print(f"Total processed records across all mapped tasks: {total_records}")
        return total_records

    # Topologi Dynamic Mapping
    partitions = retrieve_partition_keys()
    processed_data = process_partition.expand(partition_path=partitions)
    aggregate_results(processed_data)

dag_instance = dynamic_mapping_pipeline()
```

#### 7.2 Practical Enterprise Example: Custom Deferrable Sensor + S3 Remote XCom + Strict SLA

Berikut adalah implementasi arsitektur produksi:
1. **Custom S3 XCom Backend**: Mencegah data biner/JSON besar masuk ke RDBMS PostgreSQL.
2. **Custom Async Trigger & Deferrable Operator**: Menunggu tersedianya file di Amazon S3 tanpa memblokir thread worker worker slot.
3. **Resilient Production DAG**: Menggunakan *dynamic mapping*, *failure callbacks*, and *data-aware design*.

##### Berkas: `plugins/custom_xcom_backend.py`
```python
import json
import uuid
import os
from typing import Any
import boto3
from botocore.config import Config
from airflow.models.xcom import BaseXCom

class S3CustomXComBackend(BaseXCom):
    """
    Menyimpan data XCom > 1KB langsung ke S3 untuk mencegah bloat 
    pada tabel metadata RDBMS 'xcom'.
    """
    S3_BUCKET = os.getenv("AIRFLOW_XCOM_S3_BUCKET", "enterprise-airflow-xcom-prod")
    S3_PREFIX = "xcom_payloads/"
    THRESHOLD_BYTES = 1024  # Batas ambang simpan ke DB langsung vs S3

    @classmethod
    def _get_s3_client(cls):
        return boto3.client(
            "s3",
            config=Config(retries={"max_attempts": 3, "mode": "standard"})
        )

    @staticmethod
    def serialize_value(value: Any, **kwargs) -> Any:
        serialized_json = json.dumps(value, default=str)
        payload_size = len(serialized_json.encode("utf-8"))

        if payload_size > S3CustomXComBackend.THRESHOLD_BYTES:
            s3_client = S3CustomXComBackend._get_s3_client()
            key = f"{S3CustomXComBackend.S3_PREFIX}{uuid.uuid4()}.json"
            
            s3_client.put_object(
                Bucket=S3CustomXComBackend.S3_BUCKET,
                Key=key,
                Body=serialized_json.encode("utf-8"),
                ServerSideEncryption="aws:kms"
            )
            # RDBMS hanya menyimpan referensi URI S3
            reference_marker = {"__custom_remote_xcom__": True, "s3_uri": f"s3://{S3CustomXComBackend.S3_BUCKET}/{key}"}
            return BaseXCom.serialize_value(reference_marker)

        return BaseXCom.serialize_value(value)

    @staticmethod
    def deserialize_value(result: "BaseXCom") -> Any:
        raw_val = BaseXCom.deserialize_value(result)
        if isinstance(raw_val, dict) and raw_val.get("__custom_remote_xcom__"):
            s3_uri = raw_val["s3_uri"]
            bucket, key = s3_uri.replace("s3://", "").split("/", 1)
            
            s3_client = S3CustomXComBackend._get_s3_client()
            response = s3_client.get_object(Bucket=bucket, Key=key)
            return json.loads(response["Body"].read().decode("utf-8"))

        return raw_val
```

##### Berkas: `plugins/triggers/async_s3_trigger.py`
```python
import asyncio
from typing import Any, AsyncIterator, Tuple
import aioboto3
from airflow.triggers.base import BaseTrigger, TriggerEvent

class S3PrefixExistenceTrigger(BaseTrigger):
    """
    Trigger asinkron yang berjalan pada loop 'airflow-triggerer'
    menggunakan I/O asinkron aioboto3 tanpa memakan thread worker.
    """
    def __init__(self, bucket: str, prefix: str, check_interval_sec: int = 15):
        super().__init__()
        self.bucket = bucket
        self.prefix = prefix
        self.check_interval_sec = check_interval_sec

    def serialize(self) -> Tuple[str, dict[str, Any]]:
        return (
            "plugins.triggers.async_s3_trigger.S3PrefixExistenceTrigger",
            {
                "bucket": self.bucket,
                "prefix": self.prefix,
                "check_interval_sec": self.check_interval_sec
            }
        )

    async def run(self) -> AsyncIterator[TriggerEvent]:
        session = aioboto3.Session()
        while True:
            try:
                async with session.client("s3") as s3:
                    response = await s3.list_objects_v2(
                        Bucket=self.bucket,
                        Prefix=self.prefix,
                        MaxKeys=1
                    )
                    if "Contents" in response and len(response["Contents"]) > 0:
                        yield TriggerEvent({
                            "status": "success",
                            "message": f"Object ditemukan di {self.prefix}",
                            "matched_key": response["Contents"][0]["Key"]
                        })
                        return
                    
                    await asyncio.sleep(self.check_interval_sec)
            except Exception as e:
                yield TriggerEvent({"status": "error", "message": str(e)})
                return
```

##### Berkas: `dags/enterprise_payment_reconciliation.py`
```python
from datetime import datetime, timedelta
from typing import Any
from airflow.models.dag import DAG
from airflow.models.baseoperator import BaseOperator
from airflow.utils.context import Context
from airflow.exceptions import AirflowException
from plugins.triggers.async_s3_trigger import S3PrefixExistenceTrigger

def failure_slack_alert_callback(context: Context) -> None:
    """Mengirim peringatan insiden saat task instance crash."""
    task_instance = context["task_instance"]
    error = context.get("exception", "No exception trace available")
    print(f"CRITICAL: Task {task_instance.task_id} in DagRun {task_instance.dag_id} FAILED.")
    print(f"Error Context: {error}")
    # Produksi: Panggil webhook PagerDuty atau Slack SDK

class DeferrableS3Sensor(BaseOperator):
    def __init__(self, bucket: str, prefix: str, poke_interval: int = 15, **kwargs):
        super().__init__(**kwargs)
        self.bucket = bucket
        self.prefix = prefix
        self.poke_interval = poke_interval

    def execute(self, context: Context):
        # Langsung alihkan evaluasi ke triggerer process (Async)
        self.defer(
            trigger=S3PrefixExistenceTrigger(
                bucket=self.bucket,
                prefix=self.prefix,
                check_interval_sec=self.poke_interval
            ),
            method_name="execute_complete"
        )

    def execute_complete(self, context: Context, event: dict[str, Any]):
        if event.get("status") == "error":
            raise AirflowException(f"Trigger failure encountered: {event.get('message')}")
        self.log.info("Deferral complete. File berhasil divalidasi: %s", event.get("matched_key"))
        return event.get("matched_key")

class ProcessLargeLedgerOperator(BaseOperator):
    def __init__(self, ledger_partition: str, **kwargs):
        super().__init__(**kwargs)
        self.ledger_partition = ledger_partition

    def execute(self, context: Context) -> dict[str, Any]:
        self.log.info("Processing ledger partition via downstream worker: %s", self.ledger_partition)
        # Menghasilkan dataset berukuran besar yang akan di-intercept oleh S3CustomXComBackend
        large_dataset = [
            {"txn_id": f"TX_{idx}_{self.ledger_partition}", "amount": float(idx * 1.5)}
            for idx in range(100000) # Ukuran data signifikan (> 5MB)
        ]
        return {
            "partition": self.ledger_partition,
            "status": "COMPLETED",
            "records": large_dataset
        }

default_args = {
    "owner": "data-engineering-core",
    "depends_on_past": True,  # Menjamin urutan eksekusi antar interval
    "email_on_failure": False,
    "retries": 3,
    "retry_delay": timedelta(seconds=60),
    "on_failure_callback": failure_slack_alert_callback,
}

with DAG(
    dag_id="enterprise_payment_reconciliation_v1",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="0 2 * * *",  # Eksekusi harian pada pukul 02:00 UTC
    catchup=False,
    max_active_runs=1,     # Mencegah perlombaan kondisi data finansial
    tags=["finance", "payment", "tier-1"],
) as dag:

    wait_for_incoming_file = DeferrableS3Sensor(
        task_id="wait_for_incoming_payment_dump",
        bucket="enterprise-datalake-prod",
        prefix="incoming/payments/{{ ds }}/",
        poke_interval=20,
    )

    partitions = ["settlement", "chargeback", "fees", "adjustments"]

    process_partitions = ProcessLargeLedgerOperator.partial(
        task_id="process_ledger_partition",
        pool="high_memory_pool"
    ).expand(ledger_partition=partitions)

    wait_for_incoming_file >> process_partitions
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Skala Masalah
Sebuah platform perbankan digital terkemuka memproses lebih dari 12.000 siklus DAG per hari yang mencakup 150.000 eksekusi `TaskInstance`. Infrastruktur lama berbasis Apache Airflow 1.10 dengan `CeleryExecutor` pada mesin VM statis mengalami degradasi berat:
1. **Metadata DB Exhaustion**: PostgreSQL mengalami *deadlock* dan lonjakan utilisasi CPU hingga 100% akibat query polling agresif dari 400 worker process yang berebut slot antrean pada tabel `task_instance`.
2. **Worker Capacity Starvation**: Ratusan sensor standar (`HttpSensor` dan `SqlSensor`) menahan 60% slot eksekusi Celery hanya untuk menunggu data batch pihak ketiga selesai diproses. Akibatnya, tugas berprioritas tinggi mengalami *starvation* (*stuck* di state `QUEUED`).
3. **Table Bloat Ekstrem**: Tabel `xcom` di database bertumbuh 25GB per minggu karena engineer mengirimkan payload JSON API berukuran besar melalui mekanisme XCom default.

#### Transformasi Arsitektur Produksi
Tim Platform Data Engineering melakukan restrukturisasi menyeluruh:
1. **Migrasi ke Deferrable Operators**: Mengganti seluruh sensor polling berbasis blokir thread dengan operator asinkron yang dikelola oleh klaster *Airflow Triggerer* (3 replika dengan auto-balancing).
2. **Implementasi External S3 XCom Storage**: Memasang *custom XCom backend* yang langsung mengarahkan payload $\ge 1\text{ KB}$ ke bucket Amazon S3 dengan *retention lifecycle* 14 hari.
3. **Penyempurnaan Connection Pool & PgBouncer**: Mengintegrasikan PgBouncer dalam mode *transaction pooling* di depan PostgreSQL dan membatasi koneksi langsung dari proses Scheduler.
4. **Adopsi CeleryKubernetesExecutor**: Tugas-tugas ringan dijalankan di Celery worker pool statis, sedangkan tugas pengolahan data masif dijalankan secara dinamis dalam pod Kubernetes sementara (*ephemeral pods*).

#### Hasil & Metrik Performa (Sebelum vs. Sesudah)
| Metrik | Arsitektur Lama (v1.10 Static) | Arsitektur Baru (v2.8+ Modernized) | Dampak Bisnis & Efisiensi |
| :--- | :--- | :--- | :--- |
| **Worker Idle Compute Waste** | 62% alokasi CPU hanya untuk polling | < 3% alokasi CPU untuk pemantauan | Penghematan biaya cloud worker sebesar 58% ($22.000/bulan) |
| **Metadata DB Load (CPU avg)** | 85% - 100% (sering mengalami deadlock) | Stabil di 18% - 25% | Menghilangkan insiden down time database orkestrasi |
| **DAG Scheduling Latency** | Rata-rata 48 detik antre | Rata-rata 1.4 detik antre | SLA pemrosesan data real-time batch terpenuhi tepat waktu |
| **Ukuran Tabel XCom RDBMS** | 120 GB (dengan autovacuum agresif) | Konstan < 150 MB | Menghilangkan risiko disk exhaustion pada metadata DB |

---

### 9. Trade-offs

```
                  ARSITEKTUR EKSEKUSI ORKESTRASI
                                |
        +-----------------------+-----------------------+
        |                                               |
        v                                               v
[CeleryExecutor]                               [KubernetesExecutor]
  - Pros: Sangat cepat (sub-second latency)       - Pros: Isolasi pod penuh, dynamic scale,
  - Cons: Skalabilitas worker vertikal,             bebas dependency conflict antar job
          dependency collision antar job          - Cons: Overhead cold-start pod (10-30s)
        |                                               |
        +-----------------------+-----------------------+
                                |
                                v
                   [CeleryKubernetesExecutor]
             (Kompromi: Low latency untuk tugas cepat,
              Isolasi Pod K8s untuk komputasi berat)
```

| Pendekatan / Komponen | Keuntungan (*Pros*) | Kerugian (*Cons*) | Skenario Ideal |
| :--- | :--- | :--- | :--- |
| **CeleryExecutor** | Latensi startup tugas instan (*sub-detik*). Menggunakan worker pool yang sudah berjalan (*warm processes*). | Memerlukan manajemen dependencies Python global di worker image. Risiko *noisy neighbor* tinggi antar thread worker. | Pipeline dengan ribuan tugas-tugas mikro/ringan berlatensi rendah. |
| **KubernetesExecutor** | Isolasi dependensi total (setiap tugas dapat menggunakan Docker Image berbeda). Penskalaan dinamis dari 0 hingga kapasitas klaster. | *Pod spin-up overhead* (15–45 detik per tugas untuk penjadwalan pod, pulling image, dan bootstrapping). | Pipeline komputasi berat (*resource-intensive*), tugas ML, atau dependensi bahasa non-Python. |
| **Polling Sensor (Pola Lama)** | Sangat mudah diimplementasikan tanpa dependensi arsitektur tambahan. | Menahan 1 slot CPU worker penuh selama proses menunggu, membatasi skalabilitas klaster secara drastis. | Polling lokal dengan latensi pemeriksaan kurang dari 5 detik. |
| **Deferrable Operator (Pola Baru)** | Pemanfaatan sumber daya optimal. 1 proses Triggerer mampu menangani puluhan ribu penantian I/O secara asinkron. | Memerlukan arsitektur kode asinkron (`asyncio`) dan pengoperasian komponen terpisah (`airflow-triggerer`). | Komunikasi API eksternal, transfer data antar cloud, dan pipeline berbasis sinyal jarak jauh. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Kode Tingkat Atas (*Top-Level Code*) Mengakses I/O pada File DAG
- **Kesalahan Fatal**: Meletakkan koneksi database, panggilan API HTTP, atau pembacaan metadata disk di luar fungsi `execute()` pada berkas `.py` DAG.
  ```python
  # KESALAHAN FATAL: Dijalankan setiap siklus DAG Parsing (default: 30 detik sekali)
  response = requests.get("https://api.internal/v1/active-tenants")
  tenants = response.json()
  
  with DAG(...) as dag:
      # membuat task dari list tenants
  ```
- **Dampak**: *DAG Processor loop* mengalami bottleneck; CPU Scheduler melonjak 100%, memicu kegagalan heartbeat, dan pembacaan tugas tertunda secara global.
- **Solusi**: Gunakan tabel variabel Airflow, *Dynamic Task Mapping* (`expand()`), atau delegasikan pembacaan dinamis ke dalam operator tugas itu sendiri.

#### 10.2 Metadata Database Connection Pool Exhaustion
- **Penyebab**: Setiap proses worker, triggerer, webserver, dan sub-proses scheduler membuka koneksi persisten langsung ke PostgreSQL.
- **Gejala**: Log menunjukkan error: `FATAL: remaining connection slots are reserved for non-replication superuser connections`.
- **Mitigasi Arsitektur**:
  1. Tempatkan **PgBouncer** di antara komponen Airflow dan PostgreSQL menggunakan mode `pool_mode = transaction`.
  2. Batasi `sql_alchemy_pool_size` dan `sql_alchemy_max_overflow` pada berkas `airflow.cfg`.

#### 10.3 Deteksi & Penanganan Zombie Tasks
- **Penyebab**: Proses worker terhenti secara mendadak akibat *OOMKilled* (Out Of Memory) oleh kernel Linux/K8s, atau kegagalan jaringan saat mengirimkan status balik ke RDBMS.
- **Gejala Log**: `TaskInstance marked as zombie! The process that was running this task died or was killed`.
- **Troubleshooting Runbook**:
  1. Periksa metrik node Kubernetes menggunakan perintah `kubectl describe pod <worker-pod> -n airflow`.
  2. Periksa terminasi exit-code: jika `137`, tingkatkan *memory limits/requests* pada konfigurasi `pod_override` atau pindahkan komputasi berat ke engine data eksternal (Spark/Trino).
  3. Konfigurasikan batas timeout scheduler: `scheduler_zombie_task_threshold = 300` (detik).

---

### 11. Best Practices (Production Checklist)

- [ ] **Pemisahan Peran Tegas**: Engine orkestrasi **HANYA** bertindak sebagai konduktor/orkestrator, bukan pekerja komputasi (*compute engine*). Delegasikan beban ETL/ELT berat ke Spark, Trino, Snowflake, BigQuery, atau dbt Core.
- [ ] **Desain Idempoten Mutlak**: Setiap eksekusi ulang (*re-run*) DAG pada partisi tanggal yang sama (`logical_date` / `ds`) harus menghasilkan status akhir data yang identik secara deterministik tanpa duplikasi record.
- [ ] **Sanitasi Top-Level Python Code**: Pastikan tidak ada koneksi jaringan atau operasi I/O disk berat di luar method eksekusi operator. Validasi menggunakan CI/CD linting (`flake8`, `ast-parsing-check`).
- [ ] **External XCom Storage**: Konfigurasikan *remote XCom backend* (S3/GCS) dengan aturan *lifecycle* pembersihan berkas otomatis setelah 14–30 hari.
- [ ] **Implementasi PgBouncer**: Wajib menggunakan *connection pooler* transaksi di depan metadata storage PostgreSQL untuk menstabilkan ribuan koneksi konkuren.
- [ ] **Automated DAG Integrity Testing**: Jalankan validasi unit test berbasis `dagbag.process_file()` pada tahap *pull request* untuk mendeteksi *syntax error*, siklus terlarang (siklus non-asiklik), dan DAG timeout sebelum proses deployment ke klaster produksi.
- [ ] **Observabilitas & OpenLineage**: Aktifkan emisi metrik OpenLineage untuk melacak silsilah data (*data lineage*), pemetaan dependensi lintas DAG, dan integrasi katalog data enterprise (Apache Atlas / DataHub).

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun arsitektur orkestrasi produksi lokal menggunakan Docker Compose yang mencakup: Airflow Scheduler, Deferrable Triggerer, PostgreSQL, Redis, MinIO (S3-compatible storage untuk Remote XCom), serta mengimplementasikan DAG berbasis *Dynamic Task Mapping*.

#### Struktur Direktori
```
hands-on/m02/
├── docker-compose.yaml
├── config/
│   └── airflow.cfg
├── plugins/
│   ├── __init__.py
│   ├── custom_xcom_s3.py
│   └── async_triggers.py
└── dags/
    ├── dynamic_order_pipeline.py
    └── test_dag_integrity.py
```

#### Langkah 1: Siapkan Konfigurasi `hands-on/m02/docker-compose.yaml`
```yaml
version: '3.8'
x-airflow-common: &airflow-common
  image: apache/airflow:2.8.1-python3.10
  environment:
    - AIRFLOW__CORE__EXECUTOR=CeleryExecutor
    - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres:5432/airflow
    - AIRFLOW__CELERY__RESULT_BACKEND=db+postgresql://airflow:airflow@postgres:5432/airflow
    - AIRFLOW__CELERY__BROKER_URL=redis://:@redis:6379/0
    - AIRFLOW__CORE__FERNET_KEY=46BKJoQYlPPOexq0OhDZnIlNepKFf87WFwLbfzqnzq8=
    - AIRFLOW__CORE__LOAD_EXAMPLES=False
    - AIRFLOW__CORE__XCOM_BACKEND=plugins.custom_xcom_s3.MinIOCustomXComBackend
    - AWS_ACCESS_KEY_ID=minioadmin
    - AWS_SECRET_ACCESS_KEY=minioadmin
    - AWS_ENDPOINT_URL=http://minio:9000
    - AIRFLOW_XCOM_MINIO_BUCKET=airflow-xcom
  volumes:
    - ./dags:/opt/airflow/dags
    - ./plugins:/opt/airflow/plugins
    - ./logs:/opt/airflow/logs
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy

services:
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=airflow
      - POSTGRES_PASSWORD=airflow
      - POSTGRES_DB=airflow
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "airflow"]
      interval: 5s
      retries: 5
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5
    ports:
      - "6379:6379"

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

  airflow-init:
    <<: *airflow-common
    command: >
      bash -c "airflow db init &&
               airflow users create --username admin --password admin --firstname Data --lastname Engineer --role Admin --email admin@enterprise.internal"

  airflow-webserver:
    <<: *airflow-common
    command: webserver
    ports:
      - "8080:8080"
    restart: always

  airflow-scheduler:
    <<: *airflow-common
    command: scheduler
    restart: always

  airflow-triggerer:
    <<: *airflow-common
    command: triggerer
    restart: always

  airflow-worker:
    <<: *airflow-common
    command: celery worker
    restart: always

volumes:
  minio_data:
```

#### Langkah 2: Buat Modul XCom MinIO `hands-on/m02/plugins/custom_xcom_s3.py`
```python
import json
import uuid
import os
import boto3
from airflow.models.xcom import BaseXCom

class MinIOCustomXComBackend(BaseXCom):
    BUCKET_NAME = os.getenv("AIRFLOW_XCOM_MINIO_BUCKET", "airflow-xcom")
    ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "http://minio:9000")

    @classmethod
    def _client(cls):
        return boto3.client(
            "s3",
            endpoint_url=cls.ENDPOINT_URL,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
        )

    @classmethod
    def _ensure_bucket(cls):
        client = cls._client()
        try:
            client.head_bucket(Bucket=cls.BUCKET_NAME)
        except Exception:
            client.create_bucket(Bucket=cls.BUCKET_NAME)

    @staticmethod
    def serialize_value(value, **kwargs):
        MinIOCustomXComBackend._ensure_bucket()
        raw_bytes = json.dumps(value, default=str).encode("utf-8")
        
        if len(raw_bytes) > 256: # Ambang batas rendah untuk pengujian hands-on
            client = MinIOCustomXComBackend._client()
            key = f"xcom/{uuid.uuid4()}.json"
            client.put_object(Bucket=MinIOCustomXComBackend.BUCKET_NAME, Key=key, Body=raw_bytes)
            return BaseXCom.serialize_value({"__remote__": True, "key": key})
            
        return BaseXCom.serialize_value(value)

    @staticmethod
    def deserialize_value(result):
        val = BaseXCom.deserialize_value(result)
        if isinstance(val, dict) and val.get("__remote__"):
            client = MinIOCustomXComBackend._client()
            obj = client.get_object(Bucket=MinIOCustomXComBackend.BUCKET_NAME, Key=val["key"])
            return json.loads(obj["Body"].read().decode("utf-8"))
        return val
```

#### Langkah 3: Bangun Dynamic Mapped Pipeline `hands-on/m02/dags/dynamic_order_pipeline.py`
```python
from datetime import datetime
from airflow.decorators import dag, task

@dag(
    dag_id="enterprise_dynamic_order_processing",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["hands-on", "production-pattern"]
)
def order_processing_workflow():

    @task
    def extract_stores() -> list[dict[str, str]]:
        """Menghasilkan metadata toko dinamis."""
        return [
            {"store_id": "STORE_SEA_01", "region": "APAC"},
            {"store_id": "STORE_EU_02", "region": "EMEA"},
            {"store_id": "STORE_US_03", "region": "NA"}
        ]

    @task
    def process_store_transactions(store: dict[str, str]) -> dict[str, Any]:
        """Memproses transaksi toko secara paralel, menghasilkan payload > 256 bytes."""
        payload = {
            "store_id": store["store_id"],
            "region": store["region"],
            "orders": [
                {"order_id": f"ORD_{i}_{store['store_id']}", "val": i * 42.5}
                for i in range(50) # Ukuran data cukup untuk memicu remote XCom MinIO
            ]
        }
        return payload

    @task
    def consolidate_reports(store_reports: list[dict[str, Any]]) -> dict[str, int]:
        total_orders = sum(len(report["orders"]) for report in store_reports)
        print(f"Laporan berhasil dikonsolidasi. Total pesanan diproses: {total_orders}")
        return {"total_consolidated_orders": total_orders}

    stores = extract_stores()
    processed_stores = process_store_transactions.expand(store=stores)
    consolidate_reports(processed_stores)

order_processing_workflow()
```

#### Langkah 4: Eksekusi & Validasi Lingkungan
```bash
# Jalankan infrastruktur orkestrasi
cd hands-on/m02
docker compose up -d

# Periksa status container
docker compose ps

# Picu DAG via Airflow CLI di scheduler container
docker compose exec airflow-scheduler airflow dags trigger -e 2024-01-01 enterprise_dynamic_order_processing

# Periksa bucket MinIO apakah file payload XCom tersimpan
docker compose exec airflow-worker python3 -c "
import boto3, os
s3 = boto3.client('s3', endpoint_url='http://minio:9000', aws_access_key_id='minioadmin', aws_secret_access_key='minioadmin')
print(s3.list_objects_v2(Bucket='airflow-xcom')['Contents'])
"
```

---

### 13. Exercise

#### Latihan 1 (Tingkat: Easy) - AST Parsing Integrity Check
- **Tugas**: Buat berkas unit test Python `tests/test_dag_validation.py` menggunakan `pytest` dan `airflow.models.DagBag`.
- **Syarat**: Test harus memuat seluruh DAG di folder `dags/`, memverifikasi bahwa `dagbag.import_errors` bernilai nol, dan memastikan setiap DAG memiliki atribut `catchup=False` serta minimal satu tag kepemilikan tim (*owner tag*).

#### Latihan 2 (Tingkat: Medium) - Dynamic Task Concurrency Throttling
- **Tugas**: Buat pipeline orkestrasi yang melakukan dynamic mapping terhadap 100 partisi data.
- **Syarat**: Konfigurasikan sistem menggunakan *Airflow Pool* khusus bernama `isolated_api_pool` dengan kapasitas maksimal 5 slot. Pastikan pemetaan dinamis tidak pernah mengeksekusi lebih dari 5 tugas secara bersamaan demi mencegah *rate limiting* pada API backend target.

#### Latihan 3 (Tingkat: Hard) - Custom Deferrable Webhook Sensor
- **Tugas**: Kembangkan sebuah *Custom Deferrable Operator* bernama `WebhookCallbackSensor` yang terintegrasi dengan loop `asyncio`.
- **Syarat**: Operator harus memanggil endpoint HTTP eksternal untuk mendaftarkan callback token, kemudian memanggil `self.defer()` ke instance `Triggerer`. Triggerer mengevaluasi endpoint verifikasi status asinkron (`aiohttp`) setiap 10 detik hingga payload menghasilkan `status: 'READY'`. Nilai balik harus diteruskan ke downstream task tanpa memakan thread worker selama masa tunggu.

---

### 14. Challenge

#### Skenario Kasus: "Active-Active Multi-Region Resilient Orchestration Engine"

Sebuah konglomerat fintech multinasional mewajibkan platform data engineering mereka memiliki arsitektur *Disaster Recovery* (DR) berstatus **Active-Active** di dua region cloud terpisah (Region A: `ap-southeast-1`, Region B: `ap-southeast-3`). Jika satu region padam total, region yang tersisa harus mengambil alih orkestrasi 20.000 data pipeline finansial tanpa intervensi manual dan **tanpa risiko memproses data yang sama dua kali (*Strict Exactly-Once Execution*)**.

#### Kebutuhan Teknis Arsitektur:
1. **Metadata Synchronization & Conflict Resolution**: Rancang pola sinkronisasi database metadata orkestrasi (PostgreSQL) antar-region. Bagaimana Anda menangani latensi replikasi jaringan dan mencegah fenomena *split-brain* pada Scheduler di kedua region?
2. **Global Distributed Mutex Locking**: Rancang mekanisme penguncian status partisi (*Lock-leasing state*) berbasis sistem terdistribusi (misalnya memanfaatkan Spanner, DynamoDB Global Tables, atau etcd) untuk memastikan sebuah partisi tanggal hanya diklaim oleh satu Scheduler aktif.
3. **Idempotent Data Lake Sinks**: Bagaimana rancangan arsitektur penulisan downstream data lake (Apache Iceberg / Delta Lake) agar ketika terjadi failover di tengah eksekusi task, data parsial dibersihkan secara otomatis (*ACID rollback*) sebelum eksekusi pengambilalihan berjalan?
4. **Data Delivery**: Susun dokumen desain arsitektur lengkap disertai diagram topologi ASCII komprehensif, strategi *failover/fallback*, penanganan *backpressure*, dan mitigasi *distributed state corruption*.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)

1. **Apa perbedaan mendasar antara siklus `DAG File Processor` dan siklus `Scheduler` di Apache Airflow modern?**
   - *Jawaban*: `DAG File Processor` bertugas mengompilasi kode Python DAG dari disk menjadi struktur data AST serial (JSON) dan menyimpannya di DB, sementara `Scheduler` mengevaluasi status dependensi tugas di DB secara non-blocking untuk memindahkan state dari `SCHEDULED` ke `QUEUED`.

2. **Mengapa menempatkan `catchup=True` secara default pada DAG tanpa rentang tanggal batas akhir berbahaya di lingkungan produksi?**
   - *Jawaban*: Airflow akan memicu secara otomatis seluruh *DagRun* historis yang terlewat sejak `start_date` hingga hari ini, yang dapat menyebabkan ledakan komputasi mendadak (*thundering herd problem*) dan menenggelamkan kapasitas database/klaster.

3. **Komponen arsitektur manakah yang bertanggung jawab mengambil tugas dari antrean Redis pada arsitektur `CeleryExecutor`?**
   - *Jawaban*: `Celery Worker process` yang berjalan pada simpul worker.

4. **Apa fungsi utama dari `airflow.models.xcom` dan apa batasan kritis bawaannya jika digunakan tanpa backend eksternal?**
   - *Jawaban*: XCom berfungsi sebagai mekanisme pertukaran pesan status/metadata berukuran kecil antar-tugas. Batasan bawaannya adalah seluruh payload masuk ke kolom BLOB RDBMS, yang dapat memicu *table bloat*, degradasi I/O, dan kehabisan memori jika dipakai mengirim data besar.

5. **Apa yang dimaksud dengan sifat Idempoten pada rancangan sebuah tugas orkestrasi?**
   - *Jawaban*: Karakteristik di mana suatu tugas dijalankan berulang kali dengan parameter input yang sama akan selalu menghasilkan output dan status data yang identik, tanpa menghasilkan duplikasi atau inkonsistensi.

#### Bagian 2: Intermediate (5 Pertanyaan)

6. **Bagaimana cara kerja mekanisme `self.defer()` pada *Deferrable Operator* dalam menghemat worker slot?**
   - *Jawaban*: `self.defer()` melempar eksepsi khusus (`TaskDeferred`) yang menginstruksikan worker untuk menghentikan eksekusi, melepaskan slot thread/proses worker, dan mendaftarkan event penantian ke proses `Triggerer` berbasis `asyncio`.

7. **Mengapa query pencarian TaskInstance pada loop penjadwal menggunakan klausa `SELECT FOR UPDATE SKIP LOCKED`?**
   - *Jawaban*: Untuk mencegah *race condition* antar instance scheduler multi-node. Klausa ini mengunci baris tugas yang sedang diproses oleh scheduler aktif dan mengizinkan instance scheduler lain melompati baris tersebut tanpa harus menunggu (*blocking lock*).

8. **Apa perbedaan mekanisme eksekusi antara *Dynamic Task Mapping* (`expand()`) dan DAG generator script berbasis loop Python statis?**
   - *Jawaban*: Loop statis menghasilkan representasi DAG yang kaku saat waktu parsing (harus diketahui sebelum run time), sedangkan *Dynamic Task Mapping* menentukan jumlah tugas turunan secara dinamis saat runtime berdasarkan nilai aktual output tugas upstream.

9. **Sebutkan dua penyebab utama terjadinya insiden `Zombie Task` pada klaster orkestrasi Kubernetes!**
   - *Jawaban*: (1) Pod worker mengalami *OOMKilled* (Out-Of-Memory) oleh kernel Kubernetes akibat melampaui batas alokasi memori; (2) Komunikasi jaringan antara kubelet dan database metadata terputus sehingga heartbeat task melewati ambang batas toleransi.

10. **Bagaimana arsitektur *PgBouncer* mode transaksi membantu stabilitas klaster Airflow berskala enterprise?**
    - *Jawaban*: PgBouncer mengonsolidasikan ribuan koneksi jangka pendek dari berbagai proses terdistribusi (worker, scheduler, webserver) menjadi sejumlah kecil koneksi persisten ke PostgreSQL, mencegah kehabisan batas koneksi database (`max_connections`).

#### Bagian 3: Production Case Scenarios (3 Pertanyaan Kasus Analitis)

11. **Skenario Kasus A**:
    Klaster Airflow Anda mengalami kelambatan ekstrem (*DAG scheduling delay* melonjak dari 2 detik menjadi 180 detik). Saat menganalisis `top`, CPU pada pod scheduler berada pada 100%. Log menunjukkan waktu parsing file DAG memakan waktu 45 detik per loop. Kode DAG berisi pemanggilan konfigurasi parameter dari REST API eksternal di luar operator.
    - *Pertanyaan*: Analisis akar masalah teknis ini dan tuliskan langkah perbaikan arsitekturalnya!
    - *Jawaban Analitis*:
      - **Akar Masalah**: Terdapat operasi I/O jaringan sinkron (*HTTP request*) pada lingkup kode tingkat atas (*top-level code*) file DAG. Karena DAG Processor mengevaluasi file setiap siklus interval pemindaian, Scheduler memblokir seluruh proses parsing untuk menunggu respons HTTP pihak ketiga.
      - **Langkah Perbaikan**: Pindahkan pemanggilan HTTP ke dalam method `execute()` milik operator khusus, atau ambil konfigurasi tersebut sekali saja menggunakan Airflow Variable/Secret Manager yang di-cache, atau ubah konfigurasi arsitektur agar file processor berjalan terpisah (`airflow dag-processor`).

12. **Skenario Kasus B**:
    Sebuah pipeline finansial harian memproses data batch transaksi kartu kredit. Pipeline tersebut gagal di tengah jalan saat memproses data tanggal `2024-03-01` karena pemadaman listrik di datacenter. Operator menjalankan perintah `Clear Task` pada Airflow UI untuk memicu *re-run*. Setelah selesai, tim akuntansi menemukan bahwa seluruh saldo transaksi kartu kredit pada tanggal tersebut terhitung dua kali lipat.
    - *Pertanyaan*: Identifikasi kelemahan mendasar dari operator tersebut dan rancang solusi perbaikannya agar bersifat *deterministic idempotent*!
    - *Jawaban Analitis*:
      - **Kelemahan**: Operator melakukan operasi penulisan data bertipe `INSERT` atau penambahan inkremental tanpa membersihkan data lama partisi tersebut terlebih dahulu (*non-idempotent pattern*).
      - **Solusi**: Terapkan pola *Atomic Partition Replacement* (Insert-Overwrite). Modifikasi operator agar sebelum memuat data baru, ia mengeksekusi penghapusan partisi target:
        `DELETE FROM transactions WHERE transaction_date = '{{ ds }}'; INSERT INTO ...`
        Atau manfaatkan staging table temporer dan lakukan swap partisi secara atomik di dalam satu blok transaksi database.

13. **Skenario Kasus C**:
    Platform Anda mengoperasikan 500 Celery Worker nodes. Anda menerima peringatan kapasitas disk penuh pada server PostgreSQL produksi. Investigasi menemukan ukuran tabel `xcom` melonjak hingga 450 GB. Upaya menjalankan `VACUUM FULL xcom;` mengakibatkan penguncian database total (*exclusive table lock*) yang melumpuhkan seluruh operasional data ingestion perusahaan.
    - *Pertanyaan*: Bagaimana Anda menyelesaikan krisis ini secara aman tanpa mematikan sistem, dan bagaimana desain pencegahan jangka panjangnya?
    - *Jawaban Analitis*:
      - **Solusi Krisis Segera**:
        1. Jangan gunakan `VACUUM FULL` saat jam produksi aktif karena memerlukan exclusive lock.
        2. Gunakan tool seperti `pg_repack` yang mampu mereorganisasi tabel secara online tanpa locking jangka panjang.
        3. Jalankan query pembersihan entri lama bertahap:
           `DELETE FROM xcom WHERE timestamp < NOW() - INTERVAL '7 DAYS';`
           dilanjutkan `VACUUM xcom;` standar secara berkala.
      - **Pencegahan Jangka Panjang**:
        Implementasikan *Custom Remote XCom Backend* (berbasis Amazon S3 / GCS). Ubah konfigurasi agar payload yang bernilai di atas 1 KB dialihkan penyimpanannya ke bucket Object Storage terenkripsi, sehingga tabel metadata DB hanya menyimpan penunjuk URI string berukuran kecil.

---

### 16. Summary

1. **Evolusi Arsitektur Orkestrasi**: Orkestrator modern telah beralih dari sekadar eksekutor cron monolitik menjadi *state machine* terdistribusi yang memisahkan bidang kontrol dependensi (*orchestration plane*) dari bidang komputasi data (*compute plane*).
2. **Efisiensi Eksekusi Terdistribusi**: Pemanfaatan *Deferrable Operators* dengan *Triggerer* berbasis `asyncio` mengeliminasi *busy-waiting polling*, menghemat alokasi worker slots hingga lebih dari 60%, dan memangkas biaya infrastruktur cloud secara signifikan.
3. **Ketahanan Metadata Database**: Database metadata RDBMS adalah komponen paling rentan terhadap kemacetan (*bottleneck*). Penskalaan Airflow memerlukan isolasi parsing melalui *Serialized DAGs*, penerapan *PgBouncer* mode transaksi, dan pemindahan muatan data besar dari tabel `xcom` ke *Custom Object Storage Backend*.
4. **Prinsip Idempotensi & Determinisasi**: Kegagalan adalah keniscayaan dalam komputasi terdistribusi enterprise. Pipeline harus dirancang dengan partisi waktu deterministik, *atomic overwrite*, dan kemampuan *deterministic backfilling* agar pemulihan pasca-bencana dapat dieksekusi secara instan dan aman.