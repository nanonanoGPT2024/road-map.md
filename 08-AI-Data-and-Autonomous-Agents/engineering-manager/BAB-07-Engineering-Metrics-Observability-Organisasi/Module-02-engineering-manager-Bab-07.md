# BAB 07: Engineering Metrics & Observability Organisasi
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan** *Enterprise Organizational Observability Engine* (EOOE) berbasis event-driven untuk mengekstraksi, mentransformasi, dan menganalisis telemetri siklus hidup rekayasa perangkat lunak secara *real-time*.
2. **Mengkuantifikasi Metrik DORA dan Kerangka Kerja SPACE** secara presisi matematis tanpa bias manipulasi metrik (*anti-Goodharting*), termasuk integrasi telemetri kontribusi *Autonomous Agent* dan *AI-assisted workflows*.
3. **Membangun Arsitektur Data Telemetri Produksi** menggunakan stack performa tinggi (*FastAPI, Apache Kafka, ClickHouse, Grafana*) untuk mengolah jutaan event webhook developer per hari dengan latensi query analitis sub-detik.
4. **Mendiagnosis Anomali Sistemik Organisasi** seperti *code churn overload*, *review bottleneck*, dan *cognitive debt* melalui metrik terdistribusi dan korelasi data *incident-to-commit*.

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, peserta wajib memahami:
* Konsep dasar Metrik DORA (*Deployment Frequency*, *Lead Time for Changes*, *Change Failure Rate*, *Failed Deployment Recovery Time*) dan SPACE Framework.
* Arsitektur Microservices, Git internals (commit graphs, PR lifecycles), dan CI/CD automation pipelines (GitHub Actions, GitLab CI).
* Pengetahuan menengah tentang SQL analitis (Window Functions, Aggregate Functions) dan arsitektur database kolumnar (ClickHouse atau DuckDB).
* Pemrograman Python 3.11+ tingkat lanjut (asynchronous programming, Pydantic, data pipelines).
* Prinsip dasar OpenTelemetry (tracing, metrics, context propagation).

---

### 3. Concept & Internal Architecture (Mendalam)

Observabilitas organisasi modern bukan sekadar agregasi dashboard JIRA atau grafik commit Git. Pada skala enterprise, observabilitas organisasi adalah arsitektur analitis terdistribusi yang memperlakukan interaksi manusia, *autonomous coding agents*, dan infrastruktur CI/CD sebagai stream data telemetri yang terpadu.

```
       [SOURCE SYSTEMS]                     [INGESTION & BUFFER]              [ANALYTICS ENGINE]           [CONSUMPTION LAYER]
+------------------------------+
| GitHub / GitLab Webhooks     |--->\
| (Push, PR, Review, Merge)    |     \
+------------------------------+      \     +--------------------+          +---------------------+       +----------------------+
| CI/CD Runners Telemetry      |------->--->| Ingestion Gateway  |--------->| ClickHouse Cluster  |------>| Executive BI Dash    |
| (Action Runs, Build Steps)   |      /     | (FastAPI + Kafka)  | Streaming| (Normalized Engine  |       | (Grafana / Apache    |
+------------------------------+     /      +--------------------+          |  MergeTree Engines) |       |  Superset)           |
| Opsgenie / PagerDuty / Sentry|--->/                                       +---------------------+       +----------------------+
| (Incidents, Post-mortems)    |                                                      ^                              |
+------------------------------+                                                      |                              v
| AI Agent Traces / Copilot    |------------------------------------------------------+                   +----------------------+
| (Token Churn, Prompt Latency)|                                                Direct / Batch Sync       | Real-time Alerts     |
+------------------------------+                                                                          | (Slack / PagerDuty)  |
                                                                                                          +----------------------+
```

#### Komponen Kunci Arsitektur EOOE (Enterprise Organizational Observability Engine):

1. **Ingestion & Signature Validation Gateway**: Endpoint stateless berlatensi rendah yang memvalidasi otentisitas payload eksternal (menggunakan HMAC SHA-256) untuk mencegah injeksi metrik palsu, melakukan *schema validation*, dan membungkus event ke dalam format standar *CloudEvents*.
2. **Buffer & Stream Processing (Kafka / Redpanda)**: Memastikan de-coupling antara sistem penyedia event (VCS, Issue Tracker) dan sistem penyimpanan analitis, menangani *burst traffic* ketika puluhan repositori melakukan merger bersamaan.
3. **Storage Engine Kolumnar (ClickHouse)**: Menggantikan database relasional tradisional. ClickHouse dioptimalkan untuk query analitis skala masif (agregasi persentil, time-bucket rollup) dengan kompresi data hingga 80% menggunakan *ReplacingMergeTree* dan *AggregatingMergeTree*.
4. **Calculated Semantic Layer**: Lapisan matematis yang mengekstrak siklus kerja secara objektif:
   * **Cycle Time Decomposition**: $\text{Lead Time} = T_{\text{first\_commit\_to\_open\_pr}} + T_{\text{pr\_review\_latency}} + T_{\text{ci\_execution}} + T_{\text{deployment}}$.
   * **Cognitive Load Index (CLI)**: Rasio kompleksitas perubahan terhadap waktu inspeksi manusia:
     $$\text{CLI} = \frac{\Delta \text{Lines of Code} \times \text{Files Changed}}{\text{Total Human Review Time (mins)} \times \text{Reviewer Count}}$$
   * **Agent Churn Ratio (ACR)**: Kuantifikasi kode yang dihasilkan oleh Autonomous AI Agent yang di-revert atau diubah oleh engineer manusia dalam kurun waktu $\le 48\text{ jam}$.

---

### 4. Why & What

#### Mengapa Observabilitas Organisasi Berbasis Event Mutlak Diperlukan?
Pendekatan konvensional mengevaluasi produktivitas rekayasa menggunakan metrik vanity seperti *Lines of Code* (LoC) atau *Story Points Velocity*. Pendekatan ini rentan terhadap **Hukum Goodhart**: *"Ketika sebuah ukuran dijadikan target, ia berhenti menjadi ukuran yang baik."*

Dalam era adopsi AI Agent dan *Autonomous Code Generation*, masalah bertambah kompleks:
* Volume commit meningkat drastis, namun *time-to-production* sering kali stagnan atau memburuk akibat *review fatigue*.
* Kerusakan arsitektur tersembunyi karena kode yang digenerasi AI tampak valid secara sintaksis tetapi melanggar batasan konkurensi atau arsitektur domain.
* Metrik DORA standar gagal membedakan antara *deployment mikro* tanpa nilai fungsional dan *fitur bernilai tinggi*.

#### Apa yang Dibangun?
Sistem telemetri enterprise yang menyatukan empat pilar data:
1. **Signal Throughput** (Volume PR, Merge Interval, Deployment Velocity).
2. **Signal Quality & Stability** (Change Failure Rate, Mean Time to Recovery, Rollback Ratio).
3. **Human & Agent Collaboration** (Review Turnaround, AI Churn, Context Switching Overhead).
4. **Cognitive Load & Systemic Bottlenecks** (WIP per engineer, Queue Delay CI/CD).

---

### 5. How (Workflow Detail)

Alur pemrosesan end-to-end data telemetri rekayasa:

```
[Developer / Agent]
        |
        v
[Push / Pull Request] ---> Webhook Event emitted
                                |
                                v
                [FastAPI Ingestion Gateway]
                    |
                    +--> Verifikasi Signature (HMAC)
                    +--> Normalisasi ke Event Schema
                    +--> Enqueue ke Broker (Kafka Topic: `eng.telemetry.raw`)
                                |
                                v
                    [Event Stream Consumer]
                        |
                        +--> Parsing Entity Graph (User, Repo, PR, Commit)
                        +--> Deduplikasi Event
                        +--> Batch Insert ke ClickHouse Table: `engineering_events`
                                |
                                v
                    [Analytical Aggregator (ClickHouse MV)]
                        |
                        +--> Materialized View: `dora_lead_time_mv`
                        +--> Materialized View: `dora_cfr_mv`
                        +--> Materialized View: `agent_churn_mv`
                                |
                                v
                    [Engineering Management Dashboard & Automated Alerts]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Air Traffic Control (ATC) vs. Spidometer Kendaraan
* **Metrik Tradisional (LoC, Velocity)** seperti spidometer di dashboard mobil pengemudi: hanya mengukur seberapa cepat roda berputar di tempat, tanpa memberi informasi apakah mobil berjalan ke arah jurang atau terjebak macet.
* **Organizational Observability** bekerja seperti **Air Traffic Control (ATC) Radar System**:
  * Radar melacak posisi seluruh pesawat (PR dan Task),
  * Kecepatan angin dan cuaca buruk (Technical Debt, Flaky Tests),
  * Antrean runway untuk take-off dan landing (CI/CD pipeline queue dan deployment gates),
  * Peringatan tabrakan dini (Merge conflicts, cross-service regression).

#### Flow State Visualizer:
```
Commit  ----(Lead Time for Changes)----> Prod
[C1] -> [C2] -> [PR Open] ----> [PR Approved] ----> [Merged] ----> [CI/CD] ----> [Deploy Prod]
                 |                  |                  |               |                |
                 +-- Review Latency +                  +-- Build Queue +                |
                                                                                        v
                                                                             [Health Check OK?]
                                                                             /                \
                                                                          (YES)               (NO)
                                                                            |                  |
                                                                        Success             Incident
                                                                                      (Triggers MTTR Metric)
```

---

### 7. Practical Example (Kode Standar Industri)

Di bawah ini adalah implementasi sistem produksi untuk menerima webhook VCS, menormalisasi data, menyimpannya di ClickHouse, dan menghitung Metrik DORA secara real-time.

#### 1. Ingestion Gateway & Ingestion Logic (`collector/main.py`)
```python
import hmac
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Optional
from fastapi import FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
import clickhouse_connect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelemetryCollector")

app = FastAPI(title="Engineering Telemetry Ingestion Engine", version="2.0.0")

# Setup ClickHouse Client
ch_client = clickhouse_connect.get_client(
    host="localhost", port=8123, username="default", password=""
)

WEBHOOK_SECRET = "production_super_secret_key_12345"

class CloudTelemetryEvent(BaseModel):
    event_id: str
    event_source: str
    event_type: str
    actor: str
    repository: str
    timestamp: datetime
    metadata_json: str

def verify_github_signature(payload_body: bytes, header_signature: Optional[str]) -> bool:
    if not header_signature:
        return False
    sha_name, signature = header_signature.split("=")
    if sha_name != "sha256":
        return False
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

@app.post("/api/v1/telemetry/github", status_code=status.HTTP_202_ACCEPTED)
async def consume_github_webhook(
    request: Request,
    x_hub_signature_256: Annotated[Optional[str], Header()] = None,
    x_github_event: Annotated[Optional[str], Header()] = None,
    x_github_delivery: Annotated[Optional[str], Header()] = None,
):
    body = await request.body()
    
    # 1. Cryptographic Authentication
    if not verify_github_signature(body, x_hub_signature_256):
        logger.error(f"Unauthorized payload attempt. Delivery ID: {x_github_delivery}")
        raise HTTPException(status_code=403, detail="Invalid HMAC Signature")

    payload = json.loads(body.decode("utf-8"))
    
    # 2. Extract Event Core Attributes
    repo_name = payload.get("repository", {}).get("full_name", "unknown")
    sender = payload.get("sender", {}).get("login", "unknown")
    
    # Handle agentic attribution (e.g., Dependabot, Copilot workspace, internal coding agents)
    is_agent = sender.endswith("[bot]") or "agent" in sender.lower()
    actor_type = "autonomous_agent" if is_agent else "human"
    
    event_time = datetime.now(timezone.utc)
    
    # 3. Transform to Uniform Data Model
    telemetry_data = [
        x_github_delivery or "gen-" + str(datetime.now().timestamp()),
        "github",
        x_github_event or "unknown",
        f"{actor_type}:{sender}",
        repo_name,
        event_time,
        json.dumps(payload)
    ]

    # 4. Ingest directly to ClickHouse (Batching buffer abstraction simplified for example)
    try:
        ch_client.insert(
            table="engineering_telemetry_events",
            data=[telemetry_data],
            column_names=["event_id", "event_source", "event_type", "actor", "repository", "timestamp", "metadata_json"]
        )
        logger.info(f"Successfully tracked event: {x_github_event} for repo: {repo_name}")
    except Exception as e:
        logger.error(f"ClickHouse ingestion failure: {str(e)}")
        raise HTTPException(status_code=500, detail="Database write failure")

    return {"status": "persisted", "delivery_id": x_github_delivery}
```

#### 2. DDL Schema & Optimized Analytical Engine (`schema/clickhouse.sql`)
```sql
-- Database Initialization
CREATE DATABASE IF NOT EXISTS telemetry_engine;
USE telemetry_engine;

-- Raw Telemetry Table
CREATE TABLE IF NOT EXISTS engineering_telemetry_events (
    event_id String,
    event_source LowCardinality(String),
    event_type LowCardinality(String),
    actor LowCardinality(String),
    repository LowCardinality(String),
    timestamp DateTime64(3, 'UTC'),
    metadata_json String
) ENGINE = ReplacingMergeTree()
ORDER BY (repository, event_type, timestamp, event_id);

-- Pull Request Lifecycle Flattened Engine
CREATE TABLE IF NOT EXISTS pr_lifecycle_events (
    pr_id UInt64,
    repository LowCardinality(String),
    author LowCardinality(String),
    is_agent UInt8,
    created_at DateTime64(3, 'UTC'),
    merged_at Nullable(DateTime64(3, 'UTC')),
    first_review_at Nullable(DateTime64(3, 'UTC')),
    additions UInt32,
    deletions UInt32,
    review_latency_seconds SimpleAggregateFunction(max, Nullable(Int64)),
    lead_time_seconds SimpleAggregateFunction(max, Nullable(Int64))
) ENGINE = ReplacingMergeTree()
ORDER BY (repository, pr_id);

-- Incident Tracking Table (Opsgenie / PagerDuty / Sentry integration)
CREATE TABLE IF NOT EXISTS system_incidents (
    incident_id String,
    repository LowCardinality(String),
    severity LowCardinality(String),
    started_at DateTime64(3, 'UTC'),
    resolved_at Nullable(DateTime64(3, 'UTC')),
    time_to_restore_seconds SimpleAggregateFunction(max, Nullable(Int64))
) ENGINE = ReplacingMergeTree()
ORDER BY (repository, severity, incident_id);
```

#### 3. Enterprise DORA Metrics Production Calculation (`metrics/dora_calculator.py`)
```python
import clickhouse_connect
from datetime import datetime, timedelta

ch_client = clickhouse_connect.get_client(host="localhost", port=8123)

def calculate_dora_metrics_for_team(repo: str, window_days: int = 30):
    """
    Computes rigorous DORA metrics:
    1. Deployment Frequency (Total successful releases per day)
    2. Lead Time for Changes (Median delta from first commit to production deployment)
    3. Change Failure Rate (Incidents originating from deployments / Total Deployments)
    4. Time to Restore Service (MTTR in minutes)
    """
    start_time = datetime.utcnow() - timedelta(days=window_days)
    
    query = """
    WITH 
    Deployments AS (
        SELECT 
            toDate(timestamp) as day,
            count() as deploy_count
        FROM engineering_telemetry_events
        WHERE repository = {repo:String}
          AND event_type = 'deployment_status'
          AND JSONExtractString(metadata_json, 'deployment_status', 'state') = 'success'
          AND timestamp >= {start_time:DateTime}
        GROUP BY day
    ),
    LeadTimes AS (
        SELECT
            median(lead_time_seconds) / 3600.0 AS median_lead_time_hours
        FROM pr_lifecycle_events
        WHERE repository = {repo:String}
          AND merged_at IS NOT NULL
          AND merged_at >= {start_time:DateTime}
    ),
    IncidentStats AS (
        SELECT
            count() AS total_incidents,
            median(time_to_restore_seconds) / 60.0 AS median_mttr_minutes
        FROM system_incidents
        WHERE repository = {repo:String}
          AND started_at >= {start_time:DateTime}
    ),
    DeploymentTotal AS (
        SELECT count() as total_deploys
        FROM engineering_telemetry_events
        WHERE repository = {repo:String}
          AND event_type = 'deployment_status'
          AND JSONExtractString(metadata_json, 'deployment_status', 'state') = 'success'
          AND timestamp >= {start_time:DateTime}
    )
    SELECT
        coalesce(avg(Deployments.deploy_count), 0.0) AS avg_daily_deployment_freq,
        coalesce(LeadTimes.median_lead_time_hours, 0.0) AS lead_time_hours,
        coalesce(
            (IncidentStats.total_incidents * 1.0) / nullIf(DeploymentTotal.total_deploys, 0), 0.0
        ) * 100.0 AS change_failure_rate_pct,
        coalesce(IncidentStats.median_mttr_minutes, 0.0) AS mttr_minutes
    FROM DeploymentTotal
    LEFT JOIN Deployments ON 1=1
    LEFT JOIN LeadTimes ON 1=1
    LEFT JOIN IncidentStats ON 1=1
    GROUP BY LeadTimes.median_lead_time_hours, IncidentStats.total_incidents, 
             IncidentStats.median_mttr_minutes, DeploymentTotal.total_deploys;
    """
    
    result = ch_client.query(query, parameters={"repo": repo, "start_time": start_time})
    row = result.first_row
    
    return {
        "repository": repo,
        "window_days": window_days,
        "deployment_frequency_per_day": round(row[0], 2),
        "lead_time_median_hours": round(row[1], 2),
        "change_failure_rate_percentage": round(row[2], 2),
        "mttr_median_minutes": round(row[3], 2),
    }

if __name__ == "__main__":
    metrics = calculate_dora_metrics_for_team("core-banking-payment-service", 30)
    print(metrics)
```

---

### 8. Real World Case Study

#### Konteks: Fintech Enterprise (160 Engineers, 55 Microservices)
Organisasi mengintegrasikan *Autonomous Coding Agents* ke dalam daily workflow tim untuk mempercepat refactoring kode warisan (*legacy code*).

#### Masalah: "The Velocity Mirage" (Ilusi Kecepatan)
Setelah 90 hari implementasi:
* Dashboard Engineering standar menunjukkan metrik yang tampak gemilang: **PR Volume melonjak 180%**, rata-rata LoC meningkat dari 250 baris menjadi 1.200 baris per PR.
* Namun, **Business Delivery Time** melambat 35%. 
* Nilai **Change Failure Rate (CFR)** meningkat drastis dari **3.2% menjadi 17.8%**.
* Engineer senior mengeluhkan *burnout* hebat dan kelelahan mental (*review exhaustion*).

#### Investigasi Telemetri Organisasi Lanjutan:
Engineering Manager memeriksa metrik melalui sistem EOOE:
1. **Analisis PR Distribution**:
   Agen AI menghasilkan ribuan baris kode boilerplate per PR. Engineer manusia membutuhkan rata-rata **4.2 jam review time** per PR (naik dari 45 menit), namun review mendalam terabaikan karena ukuran PR terlalu besar (*Cognitive Overload*).
2. **Korelasi Churn Code vs Incident**:
   ClickHouse mengkorelasikan commit author terhadap baris kode penyebab insiden di Sentry. Hasilnya: **72% insiden produksi berasal dari blok kode boilerplate AI** yang di-approve tanpa verifikasi unit test mendalam (*rubber-stamped PR*).
3. **Queue Latency di CI/CD**:
   Runner CI/CD overload menangani build matrix untuk ribuan commit sintetis, menyebabkan *Queue Wait Time* melonjak dari 4 menit menjadi 52 menit per commit.

#### Solusi Arsitektural & Kebijakan:
* **Membatasi Ukuran PR Agen**: Menolak PR otomatis jika perubahan melebihi 200 baris (diterapkan via API Webhook gate).
* **Menerapkan Agent Churn Ratio (ACR) SLO**: Jika kode agen di-revert atau diubah kembali $>15\%$ dalam 7 hari, agen dinonaktifkan sementara dari modul domain tersebut.
* **Metrik SPACE: Cognitive Load Guardrail**: Mengalokasikan kapasitas review maksimal 60 menit per hari per senior engineer untuk mencegah *rubber-stamping*.
* **Hasil**: Dalam 6 minggu, CFR turun kembali ke **2.8%**, Lead time membaik sebesar 48%, dan beban CI runner berkurang 65%.

---

### 9. Trade-offs & Limitations

| Dimensi | Pendekatan Ringan (Polling API Git / JIRA Plugins) | Pendekatan Enterprise EOOE (Event Stream + ClickHouse) |
| :--- | :--- | :--- |
| **Latensi Data** | Tinggi (Batch polling 6-24 jam sekali, data stale). | Real-time (Sub-detik via webhook & event streaming). |
| **Infrastruktur Overhead** | Sangat Rendah (SaaS/Out-of-the-box). | Tinggi (Membutuhkan hosting Kafka, ClickHouse, Ingestion APIs). |
| **Fleksibilitas Kustomisasi** | Rendah (Tergantung metrik bawaan vendor). | Tanpa Batas (Bebas mengkorelasikan commit, AI traces, logs, incidents). |
| **Resiko Goodharting** | Ekstrem (Metrik mudah dimanipulasi dengan split PR / fake commits). | Rendah (Korelasi multidimensi mendeteksi anomali perilaku). |
| **Data Privacy & Governance** | Data engineer dan kode terunggah ke pihak ketiga (SaaS). | Terkelola on-premise/VPC (Sesuai regulasi kepatuhan data ISO/SOC2). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum:
1. **Mengukur Individu, Bukan Sistem**: Menggunakan DORA atau metrik throughput untuk ranking performa individual engineer. Ini menghancurkan *psychological safety*, memicu manipulasi metrik (misal: memecah satu PR logis menjadi 20 PR kecil tanpa esensi).
2. **Mengabaikan Outlier (Menggunakan Arithmetic Mean)**: Rata-rata (*mean*) sangat rentan terdistorsi oleh satu incident ekstrem atau satu refactoring besar. **Wajib menggunakan Median (P50), P90, dan P95** untuk *Lead Time* dan *MTTR*.
3. **Mengabaikan "Unreviewed Merge Bypass"**: Menghitung deployment frequency tinggi sebagai kesuksesan, tanpa memvalidasi apakah kode tersebut melewati tahapan pull request atau push langsung ke trunk.
4. **Data Desinkronisasi Webhook**: Kehilangan webhook event saat deployment cluster atau network partition.

#### Troubleshooting & Diagnostic Runbook:
* **ClickHouse High Disk Usage**:
  * *Penyebab*: Partisi ReplacingMergeTree terlalu granular atau metadata JSON mentah terlalu besar.
  * *Solusi*: Buat Materialized View untuk mengekstrak atribut penting ke tabel terpisah, lalu atur TTL pada tabel raw event mentah (`ALTER TABLE engineering_telemetry_events MODIFY TTL timestamp + INTERVAL 90 DAY;`).
* **Signature Verification Failures**:
  * *Penyebab*: Reverse proxy (seperti Nginx atau AWS ALB) memodifikasi body payload atau encoding whitespace sebelum mencapai Python Ingestion Gateway.
  * *Solusi*: Baca `request.stream()` raw bytes secara langsung sebelum middleware body parsing dijalankan.

---

### 11. Best Practices (Production Checklist)

- [ ] **Kriptografi Valid**: Setiap webhook endpoint mengimplementasikan HMAC SHA-256 validation dengan rotasi secret berkala.
- [ ] **Idempotensi Total**: Setiap event memiliki deterministik `event_id` atau delivery UUID; ingest layer menggunakan deduplikasi otomatis (`ReplacingMergeTree` atau Redis de-dupe cache).
- [ ] **Privasi Engineer**: Nama engineer di-hash atau diagregasikan pada level tim untuk metrik operasional publik, mencegah perbandingan antar-individu.
- [ ] **Statistical Integrity**: Seluruh kalkulasi waktu (*Lead Time*, *MTTR*, *Review Latency*) menggunakan persentil (P50/P90), bukan average.
- [ ] **SLO Monitoring untuk Telemetry Pipeline**: Pipeline observabilitas harus memiliki SLO ketersediaan $\ge 99.9\%$ dan latensi pemrosesan $< 5\text{ detik}$.
- [ ] **Pemberian Anotasi AI**: Seluruh event kontribusi dari *Autonomous Agent* dilabeli flag `is_agent=1` untuk memisahkan analisa efisiensi tim manusia dari otomatisasi.

---

### 12. Hands-on Practice

Buat struktur direktori berikut di lingkungan lokal Anda:
`hands-on/m02/`

```bash
mkdir -p hands-on/m02/collector hands-on/m02/schema hands-on/m02/scripts
cd hands-on/m02/
```

#### Langkah 1: Jalankan Infrastruktur Lokal (Docker Compose)
Simpan file `docker-compose.yml`:
```yaml
version: '3.8'
services:
  clickhouse:
    image: clickhouse/clickhouse-server:23.8
    ports:
      - "8123:8123"
      - "9000:9000"
    environment:
      - CLICKHOUSE_DB=telemetry_engine
    ulimits:
      nofile:
        soft: 262144
        hard: 262144
```
Jalankan ClickHouse:
```bash
docker compose up -d
```

#### Langkah 2: Migrasi Schema
Simpan DDL schema SQL dari **Seksi 7 (Subseksi 2)** ke dalam `schema/clickhouse.sql`, lalu eksekusi:
```bash
docker exec -i $(docker compose ps -q clickhouse) clickhouse-client < schema/clickhouse.sql
```

#### Langkah 3: Eksekusi Ingestion Engine
Simpan kode server dari **Seksi 7 (Subseksi 1)** ke dalam `collector/main.py`.
Install dependensi dan jalankan API:
```bash
pip install fastapi uvicorn clickhouse-connect pydantic
uvicorn collector.main:app --port 8000 --reload
```

#### Langkah 4: Simulasikan Mock Webhook Event
Simpan script mock generator `scripts/emit_mock_events.py`:
```python
import hmac
import hashlib
import json
import requests

SECRET = "production_super_secret_key_12345"
URL = "http://localhost:8000/api/v1/telemetry/github"

payload = {
    "repository": {"full_name": "enterprise-org/payments-core"},
    "sender": {"login": "ai-code-agent[bot]"},
    "action": "closed",
    "pull_request": {
        "id": 9942,
        "merged": True,
        "additions": 450,
        "deletions": 120
    }
}

body = json.dumps(payload).encode("utf-8")
signature = "sha256=" + hmac.new(SECRET.encode(), msg=body, digestmod=hashlib.sha256).hexdigest()

headers = {
    "X-Hub-Signature-256": signature,
    "X-GitHub-Event": "pull_request",
    "X-GitHub-Delivery": "test-uuid-001"
}

resp = requests.post(URL, data=body, headers=headers)
print("Response Status:", resp.status_code)
print("Response Body:", resp.json())
```
Eksekusi pengujian:
```bash
python scripts/emit_mock_events.py
```

---

### 13. Exercise

#### Level Easy
Modifikasi skrip `collector/main.py` agar menolak payload jika `event_type` bukan salah satu dari: `pull_request`, `push`, `deployment_status`, atau `issues`. Berikan return status `400 Bad Request`.
* **Kriteria Selesai**: Payload valid diproses; payload ilegal ditolak sebelum query ClickHouse dieksekusi.

#### Level Medium
Tulis fungsi SQL di ClickHouse untuk menghitung **Review Bottleneck Ratio (RBR)** untuk masing-masing repositori dalam 14 hari terakhir:
$$\text{RBR} = \frac{\text{Waktu dari PR dibuat hingga First Review}}{\text{Waktu dari First Review hingga PR Merge}}$$
* **Kriteria Selesai**: Query mengembalikan repository, PR ID, dan rasio desimal. Jika rasio $> 3.0$, tandai sebagai `ANOMALY_REVIEW_STARVATION`.

#### Level Hard
Buat pipeline streaming mini yang mendeteksi **Agent Churn Loop**: Jika sebuah Autonomous Agent membuat PR yang mengubah baris kode yang sama yang dimodifikasi oleh PR lain dalam kurun waktu kurang dari 24 jam, kirim alert webhook ke endpoint simulasi tim arsitektur.
* **Kriteria Selesai**: Menggunakan ClickHouse window query `lagInFrame()` atau script Python terpisah yang mengeksekusi analisis riwayat file churn per commit hash.

---

### 14. Challenge (Tantangan Studi Kasus Nyata)

**Skenario**:
Anda memimpin divisi engineering dengan 250 engineer dan 12 Autonomous Coding Agents yang berjalan secara berkala. Pasca integrasi agen otomatis, terjadi **"Micro-Deployment Storm"**:
* Frekuensi deployment melonjak 10x lipat (membuat metrik DORA Deployment Frequency terlihat sangat baik, kategori "Elite Performer").
* Namun, setelah diaudit, 60% deployment tersebut hanyalah perubahan sintaks minor, update dependensi otomatis yang tidak signifikan, atau commit formatting.
* Pada saat yang sama, 3 insiden Severity-1 terjadi secara paralel, tetapi metrik Change Failure Rate (CFR) tampak rendah palsu (*diluted*) karena total penyebut (total deployment) membengkak masif oleh rilis-rilis mikro sintetis.

**Tugas Anda**:
1. Formulasikan metrik baru: **Meaningful Delivery Index (MDI)** dan **Adjusted Change Failure Rate (aCFR)** untuk mengeliminasi manipulasi statistik akibat *deployment storming*.
2. Rancang arsitektur telemetri yang mampu mengklasifikasikan bobot nilai perubahan produksi (*Impact-Weighted Telemetry*) secara otomatis tanpa membebani engineer dengan input manual.
3. Definisikan batas ambang alerting (*alert threshold*) yang harus dikirimkan ke Slack Engineering Leadership saat metrik produktivitas tim terindikasi terdistorsi oleh aktivitas agen sintetis.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Apa alasan utama penggunaan nilai *Median* dibandingkan *Mean* dalam kalkulasi DORA Lead Time for Changes?
   - A. Median lebih mudah dihitung secara komputasi.
   - B. Median tidak terdistorsi secara ekstrem oleh outlier (pencilan data).
   - C. Median menjamin nilai metrik selalu lebih kecil.
   - D. Mean tidak didukung oleh database kolumnar seperti ClickHouse.

2. Apa fungsi dari verifikasi header `X-Hub-Signature-256` pada endpoint webhook telemetri?
   - A. Menjaga kompresi data JSON payload.
   - B. Mengenkripsi isi pesan agar database tidak dapat membacanya.
   - C. Memvalidasi bahwa payload benar-benar berasal dari VCS terpercaya menggunakan kriptografi HMAC SHA-256.
   - D. Mengubah format string menjadi CloudEvents secara otomatis.

3. Di dalam kerangka kerja SPACE, apa kepanjangan dari akronim tersebut?
   - A. Speed, Performance, Agility, Cost, Efficiency.
   - B. Satisfaction, Performance, Activity, Communication/Collaboration, Efficiency/Flow.
   - C. Security, Pipeline, Architecture, Continuous Integration, Execution.
   - D. Scalability, Parallelism, Availability, Consistency, Elasticity.

4. Database jenis apakah ClickHouse, dan mengapa ia ideal untuk telemetri organisasi?
   - A. Graph database, cocok untuk pemetaan relasi antar-developer.
   - B. Document Store NoSQL, fleksibel untuk unstructured logs.
   - C. Column-oriented DBMS, sangat cepat untuk query analitis agregasi data historis masif.
   - D. In-Memory Key-Value store, memprioritaskan latensi tulis microsecond.

5. Dalam terminologi DORA, bagaimana Change Failure Rate (CFR) didefinisikan?
   - A. Jumlah unit test yang gagal dibagi total run build.
   - B. Persentase deployment ke production yang mengakibatkan insiden, rollback, atau degradasi layanan mendesak.
   - C. Rasio PR yang ditolak saat proses code review.
   - D. Rata-rata waktu yang dibutuhkan developer untuk memperbaiki bug staging.

#### Intermediate (5 Pertanyaan)
6. Manakah dari skenario berikut yang mencerminkan pelanggaran langsung terhadap **Hukum Goodhart** dalam observabilitas organisasi?
   - A. Tim mengoptimalkan waktu build Docker untuk mempercepat deployment.
   - B. EM memberikan bonus kepada developer yang membuat jumlah Pull Request terbanyak, menyebabkan engineer memecah 1 PR fungsional menjadi 15 PR artifisial.
   - C. Tim menetapkan SLO latensi API di bawah 200 ms.
   - D. Penggunaan ReplacingMergeTree untuk menghapus data duplikasi webhook.

7. Jika Lead Time for Changes tim Anda sangat panjang, namun CI Execution Time hanya 4 menit, di manakah letak investigasi pertama Anda pada fase lifecycle?
   - A. Kapasitas RAM pada server ClickHouse.
   - B. Review Latency (Waktu antre dari PR dibuka hingga review pertama diselesaikan oleh rekan kerja).
   - C. Penambahan jumlah runner Docker CI.
   - D. Algoritma enkripsi HMAC SHA-256 pada gateway.

8. Bagaimana *Cognitive Load* dapat diidentifikasi secara kuantitatif melalui telemetri Pull Request?
   - A. Menghitung jumlah kata dalam komentar review.
   - B. Membandingkan ukuran perubahan (diff LoC) yang masif dengan durasi review yang sangat singkat (menandakan reviewer kewalahan dan melakukan *rubber-stamping*).
   - C. Mengukur waktu developer mengetik kode di editor.
   - D. Menghitung durasi pertemuan harian (standup meeting).

9. Apa fungsi engine table `ReplacingMergeTree` di ClickHouse dalam menangani webhook Git?
   - A. Menghapus data secara permanen setiap 24 jam.
   - B. Mengganti semua query SQL lama secara dinamis.
   - C. Melakukan deduplikasi data secara background berdasarkan kolom sorting key saat terjadi pengiriman webhook ulang (*idempotency handling*).
   - D. Membagi data ke dalam partisi disk yang terenkripsi.

10. Ketika mengintegrasikan *Autonomous AI Coding Agent*, apa arti metrik *Agent Churn Ratio* yang tinggi (>40%)?
    - A. Agen menghasilkan kode dengan kecepatan di atas rata-rata manusia.
    - B. Kode yang dibuat oleh AI memiliki kualitas rendah atau salah paham konteks, sehingga sebagian besar harus di-revert atau ditulis ulang oleh manusia dalam hitungan jam.
    - C. Pipeline CI/CD berjalan terlalu lambat untuk kapasitas agen.
    - D. Database telemetri kehabisan memori komputasi.

#### Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1**:
    Tim Core Banking mengklaim nilai DORA MTTR mereka adalah 12 menit (*Elite*). Namun, pelanggan komplain transaksi gagal selama 4 jam berturut-turut pada hari Jumat.
    Setelah diaudit, tim mendefinisikan insiden dimulai saat *tiket status incident di JIRA dibuat* (yang baru dibuat 3 jam 40 menit setelah sistem down) dan ditutup saat *engineer mengumumkan investigasi selesai* (meskipun patch belum dirilis). 
    Bagaimana Anda mendesain ulang telemetri MTTR agar objektif?
    - A. Menghapus metrik MTTR dari dashboard dan menggantinya dengan LoC.
    - B. Mengintegrasikan MTTR langsung dengan APM alert start time (PagerDuty/Datadog) hingga titik *Production Health Check Status = 200 OK* pada deployment perbaikan.
    - C. Memaksa tim JIRA untuk selalu standby 24 jam.
    - D. Menghitung MTTR semata-mata dari durasi build CI/CD pipeline.

12. **Skenario 2**:
    Setelah mengadopsi AI Coding Assistant secara luas, Lead Time tim Anda turun dari 48 jam menjadi 12 jam. Namun, pada saat yang sama, *Sentry Error Tracking* mencatat lonjakan exception null-pointer di production sebesar 300%.
    Langkah taktis apa yang harus diambil oleh Engineering Manager berdasarkan data observabilitas ini?
    - A. Melarang penggunaan seluruh AI tool di perusahaan.
    - B. Menerapkan threshold otomatis: PR dengan kontribusi AI wajib memiliki cakupan test coverage $\ge 90\%$ dan menyertakan korelasi metrik *mutation testing score* sebelum diizinkan merge.
    - C. Mengurangi kriteria review manusia agar Lead Time bisa turun menjadi 6 jam.
    - D. Menghapus integrasi Sentry dari pipeline ClickHouse.

13. **Skenario 3**:
    Cluster ClickHouse telemetri Anda mengalami lonjakan memori (OOM Crash) setiap hari Senin jam 09:00 pagi saat para eksekutif membuka dashboard Grafana. Query yang berjalan adalah kalkulasi Lead Time 90 hari dengan grouping per developer.
    Apa perbaikan arsitektural yang paling efisien?
    - A. Mengganti ClickHouse dengan database PostgreSQL standar.
    - B. Membuat ClickHouse *Materialized View* yang melakukan pra-agregasi metrik per minggu pada tingkat tim, dan mengarahkan dashboard ke view tersebut tanpa mengeksekusi raw table scan per individu.
    - C. Melarang eksekutif membuka Grafana di jam kerja sibuk.
    - D. Menghapus data telemetri historis yang berusia lebih dari 7 hari.

---

### Kunci Jawaban Quiz

1. **B** - Median kebal terhadap distorsi nilai ekstrem/pencilan.
2. **C** - Otentikasi kriptografis HMAC memastikan pengirim webhook adalah Git provider resmi yang sah.
3. **B** - Satisfaction, Performance, Activity, Communication/Collaboration, Efficiency/Flow.
4. **C** - ClickHouse adalah database kolumnar yang sangat optimal untuk scan dan agregasi data analitis analitik time-series skala besar.
5. **B** - Persentase deployment ke production yang memicu insiden atau membutuhkan intervensi/rollback darurat.
6. **B** - Memberi insentif pada volume PR memicu manipulasi artifisial tanpa menambah nilai bisnis riil.
7. **B** - Antrean review manusia (PR review latency) adalah titik hambatan utama saat CI build time sudah sangat singkat.
8. **B** - PR besar yang di-approve dalam tempo kilat menandakan pengabaian verifikasi mendalam akibat kelelahan kognitif.
9. **C** - ReplacingMergeTree mendeduplikasi baris data duplikat secara background berdasarkan Order Key.
10. **B** - Churn tinggi pada output agen menandakan kode artifisial yang tidak stabil dan membutuhkan intervensi ulang manusia.
11. **B** - MTTR sejati harus ditarik secara sistemis dari waktu deteksi anomali telemetri pertama hingga verifikasi kesehatan sistem di endpoint produksi.
12. **B** - Menambahkan guardrail objektif berupa mutation testing & automated test coverage khusus untuk menyeimbangkan akselerasi kode agen sintetis.
13. **B** - Materialized Views menghitung roll-up metrik di awal saat data ditulis, mengubah query berat berbiaya miliaran baris menjadi pembacaan ringkas sub-detik.

---

### 16. Summary

* **Observabilitas Organisasi** mengubah manajemen rekayasa dari intuisi subjektif menjadi disiplin berbasis data kuantitatif yang presisi, menggunakan arsitektur event-driven terdistribusi.
* **Metrik DORA & SPACE** harus diimplementasikan secara beriringan: DORA mengukur throughput dan stabilitas sistem, sedangkan SPACE menjamin keberlanjutan manusiawi, kolaborasi, dan pencegahan *burnout*.
* Masuknya **Autonomous AI Coding Agents** menuntut penyesuaian metrik: metrik volume mentah (LoC, Total PR) telah usang; fokus beralih ke *Cognitive Load Index*, *Review Latency*, dan *Agent Churn Ratio*.
* Membangun EOOE internal menggunakan arsitektur pipeline modern (**FastAPI, Kafka, ClickHouse**) memberikan kedaulatan data penuh, fleksibilitas korelasi lintas sistem (VCS, CI, APM, Insiden), dan perlindungan mutlak dari bahaya manipulasi Hukum Goodhart.