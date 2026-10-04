# BAB 09: DevRel Metrics, Business Impact & Attribution
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur *Developer Telemetry & Identity Resolution Pipeline* berskala enterprise untuk menghubungkan jejak aktivitas anonim pengembang (*developer journey*) dengan metrik bisnis inti (*Product-Qualified Leads/PQL*, *Net Retention Rate/NRR*, dan konsumsi API).
- Mengembangkan model atribusi multi-sentuh (*Multi-Touch Attribution/MTA*) deterministik dan probabilistik (termasuk *Markov Chain Attribution*) khusus untuk ekosistem pengembang.
- Membangun pipeline pemrosesan *event-driven telemetry* performa tinggi menggunakan Apache Kafka/Redpanda, ClickHouse, dan dbt.
- Mengatasi tantangan identifikasi lintas platform (*identity stitching*) antara repositori kode publik (GitHub/GitLab), dokumentasi teknis, CLI/SDK telemetry, dan *production product database*.
- Mengoperasikan sistem pemantauan dampak DevRel yang aman, patuh regulasi privasi (GDPR/CCPA, Zero-PII leak), dan tahan terhadap manipulasi metrik semu (*vanity metrics*).

---

### 2. Prerequisite

Peserta wajib memiliki pemahaman mendalam tentang:
- **Distributed Event Streaming**: Arsitektur Apache Kafka atau Redpanda (Producer, Consumer Group, Partitioning, Idempotency).
- **Modern Data Warehousing**: ClickHouse, Snowflake, atau Google BigQuery (khususnya *analytical SQL*, window functions, dan optimasi *columnar storage*).
- **Backend & Data Engineering**: Python 3.11+ (FastAPI, Pydantic, Pandas, NumPy, NetworkX) dan dbt (*data build tool*).
- **Web Protocols & Security**: HTTP Webhooks, HMAC signature verification, OAuth 2.0, OpenTelemetry dasar.
- **Konsep DevRel Core**: Siklus hidup pengembang (*Developer Funnel*: Discover, Evaluate, Learn, Build, Scale).

---

### 3. Concept & Internal Architecture

Menghitung dampak bisnis Developer Relations (DevRel) memerlukan perubahan paradigma dari metrik pemasaran konvensional (*lead capture via form*) menuju *developer-first telemetry*. Pengembang menolak pengisian formulir prospek (*gated content*), memblokir pelacak skrip web berbasis cookie pihak ketiga, dan sering kali menjelajahi platform menggunakan akun anonim atau alias yang berbeda-beda sebelum akhirnya melakukan registrasi produk.

Arsitektur atribusi DevRel produksi bertumpu pada tiga pilar utama:

```
+-----------------------------------------------------------------------------------+
|                        DEVREL IDENTITY GRAPH ENGINE                               |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [Touchpoint 1: GitHub]   [Touchpoint 2: Docs]   [Touchpoint 3: CLI]              |
|   github_id: "octo_dev"     visitor_id: "ck_981"   cli_install_id: "uuid-v4"      |
|           \                         |                         /                   |
|            \                        |                        /                    |
|             v                       v                       v                     |
|        +---------------------------------------------------------+                |
|        |           Identity Stitching & Resolution Table         |                |
|        |---------------------------------------------------------|                |
|        | canonical_developer_id: "dev_8829103cba"                |                |
|        | aliases: ["octo_dev", "ck_981", "uuid-v4"]              |                |
|        | corporate_email: "lead@enterprise.internal"             |                |
|        | first_seen: 2024-01-10T08:00:00Z                        |                |
|        +---------------------------------------------------------+                |
|                                     |                                             |
|                                     v                                             |
|                      +-----------------------------+                              |
|                      |  Multi-Touch Attribution    |                              |
|                      |  (Markov Chains / W-Shaped) |                              |
|                      +-----------------------------+                              |
|                                     |                                             |
|                                     v                                             |
|                      +-----------------------------+                              |
|                      | Business Impact & RevOps    |                              |
|                      | API ARR / Enterprise Deals  |                              |
|                      +-----------------------------+                              |
+-----------------------------------------------------------------------------------+
```

#### 3.1. Developer Identity Graph (Identity Resolution Engine)
Developer Identity Graph memetakan keterkaitan antar entitas berikut:
- **GitHub Handle / Commit SHA**: Diperoleh melalui webhook (Stars, Forks, Issues, Pull Requests).
- **Anonymous Client Fingerprint**: ID pseudo-anonim berbasis sesi peramban di dokumentasi teknis (didukung oleh *first-party server-side cookies*).
- **CLI Ephemeral UUID**: Dihasilkan saat perintah seperti `cli-tool auth login` atau `cli-tool init` pertama kali dieksekusi secara lokal.
- **Package Manager IP/Mirror Telemetry**: Agregasi pengunduhan *library* dari PyPI, npm, atau Docker Hub (menggunakan log metadata non-PII).
- **Workspace/Organization ID**: ID akun produksi di sistem *billing* (Stripe/Chargebee) dan database inti aplikasi.

Penyatuan identitas (*identity stitching*) dilakukan melalui dua metode:
1. **Deterministik**: Dicapai saat pengembang mengeksekusi aksi yang menyatukan dua titik data secara pasti, misalnya: masuk ke portal dokumentasi menggunakan GitHub OAuth, atau mengautentikasi CLI lokal dengan token akun yang menghubungkan `cli_install_id` dengan `user_id` di database produksi.
2. **Probabilistik**: Menghubungkan sesi anonim docs dengan pembuatan API Key baru dalam jendela waktu sempit ($\Delta t \le 15 \text{ menit}$) dari subnet IP korporat yang identik (khusus jaringan non-VPN/fixed office enterprise).

#### 3.2. Model Atribusi Algoritmik (Markov Chain Removal Effect)
Model atribusi statis (*First-Touch*, *Last-Touch*, atau *Linear*) memiliki kelemahan struktural dalam DevRel:
- *First-Touch* mendistorsi bobot ke event publikasi (misal: cuitan pengumuman atau video YouTube), mengabaikan dokumentasi API yang memfasilitasi integrasi nyata.
- *Last-Touch* mendistorsi bobot ke pengunduhan SDK atau halaman pembayaran, mengabaikan upaya berbulan-bulan penulisan tutorial teknis oleh Developer Advocates.

Oleh karena itu, sistem produksi enterprise memanfaatkan **Markov Chain Attribution**. Seluruh perjalanan pengembang dimodelkan sebagai *directed graph* state transisi terbobot:

$$P(S_j \mid S_i) = \frac{N_{i \to j}}{\sum_{k} N_{i \to k}}$$

Di mana $N_{i \to j}$ adalah jumlah transisi dari state touchpoint $S_i$ ke $S_j$. Efek penghapusan (*Removal Effect*) dari suatu touchpoint DevRel $S_x$ dihitung dengan mengukur penurunan probabilitas konversi total ($L$) saat node $S_x$ dihapus dari graf transisi:

$$\text{Removal Effect}(S_x) = 1 - \frac{L(\text{Graf tanpa } S_x)}{L(\text{Graf Utuh})}$$

Bobot kontribusi atribusi terhadap pendapatan (ARR) atau aktivasi API untuk touchpoint $S_x$ dinormalisasi sebagai:

$$\text{Weight}(S_x) = \frac{\text{Removal Effect}(S_x)}{\sum_{y} \text{Removal Effect}(S_y)}$$

---

### 4. Why & What

| Dimensi | Pendekatan DevRel Tradisional (Vanity-Based) | Pendekatan Enterprise Data-Driven (Impact-Based) |
| :--- | :--- | :--- |
| **Metrik Utama** | GitHub Stars, Tayangan YouTube, Jumlah Peserta Meetup. | PQL (*Product-Qualified Leads*), Konsumsi Token/Detik API, TTFW (*Time to First "Hello World"*), Kontribusi ARR. |
| **Pelacakan Jejak** | Google Analytics terisolasi, data terfragmentasi di repositori tim. | *Event-driven unified developer lakehouse* (ClickHouse/Snowflake + Kafka). |
| **Model Atribusi** | Tidak ada atribusi langsung; asumsi korelasi sepihak. | Multi-Touch Attribution (W-Shaped & Markov Chains berbasis Graph). |
| **Integrasi RevOps** | Terisolasi dari tim Penjualan/Enterprise Solutions. | Terhubung dua arah dengan CRM (Salesforce/HubSpot) dan Data Mart FinOps. |
| **Integritas Data** | Rentan terhadap manipulasi bot GitHub dan lalu lintas scraping web. | Verifikasi tanda tangan kriptografis (HMAC SHA-256), *anomaly detection*, dan validasi skema runtime. |

---

### 5. How (Workflow Detail)

Alur kerja implementasi atribusi DevRel pada lingkungan enterprise mencakup tahapan berikut:

```
[External Sources]           [Ingestion Layer]              [Processing & Graph]               [Serving Layer]
+------------------+         +------------------+         +----------------------+          +-------------------+
| GitHub Webhooks  | ------> |                  | ------> | Stream Deduplication | -------> | ClickHouse        |
| Docs Telemetry   | ------> | Edge API Gateway |         | & Schema Validation  |          | (OLAP Engine)     |
| CLI OpenTelemetry| ------> | (FastAPI Engine) |         | (Redpanda / Kafka)   |          +---------+---------+
| Discord/Forum    | ------> |                  |         +----------+-----------+                    |
+------------------+         +--------+---------+                    |                              |
                                      |                              v                              v
                             [HMAC Signature]             +----------------------+          +-------------------+
                             [Auth Validation]            | Identity Resolution  | -------> | dbt Transformation|
                                                          | Graph (DuckDB/dbt)   |          | MTA Markov Models |
                                                          +----------------------+          +---------+---------+
                                                                                                    |
                                                                                                    v
                                                                                            +-------------------+
                                                                                            | RevOps & CRM      |
                                                                                            | Attribution Sync  |
                                                                                            +-------------------+
```

1. **Ingestion Layer**: Menerima muatan data (*payload*) telemetry dari GitHub App/Webhooks, SDK Docs, dan CLI client via endpoint API Gateway berkinerja tinggi. Memverifikasi integritas *payload* menggunakan HMAC-SHA256.
2. **Buffering Layer**: Mengirimkan raw event ke Kafka/Redpanda topic `telemetry.devrel.raw` dengan mekanisme *idempotent producer*.
3. **Stream Deduplication & Enrichment**: Mengurai payload, memisahkan atribut identitas (email, alias, IP corporate, cookie UUID), menyamarkan data sensitif (hashing PII), lalu memasukkannya ke ClickHouse.
4. **Graph Identity Resolution**: Worker terjadwal (atau Flink/dbt-run) mengeksekusi resolusi graf untuk memperbarui tabel asosiasi kanonikal `dim_developers`.
5. **Attribution Modeling**: Pipeline dbt menghitung matriks konversi transisi status (*conversion paths*), mengeksekusi algoritma Markov Chain Removal Effect, dan menetapkan nilai nominal pendapatan (ARR) atau token API ke tiap event DevRel.
6. **Reverse-ETL / Serving**: Menyinkronkan metrik skor keterlibatan pengembang (*Developer Intent Score*) dan atribusi kampanye langsung ke CRM tim Enterprise Sales.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan Anda adalah mandor konstruksi gedung pencakar langit. 
- *Pemasaran B2B Tradisional* menganggap setiap orang yang melihat baliho gedung sebagai calon pembeli unit apartemen.
- *DevRel Attribution Engine* bekerja layaknya penyelidik forensik: Tim arsitek anonim datang memeriksa kualitas beton di malam hari (membaca dokumentasi API), mencoba sampel paku keling secara privat di bengkel mereka (menginstal CLI & clone sample code), lalu memberikan rekomendasi tertulis kepada direktur investasi untuk membeli 10 lantai gedung tersebut. Atribusi DevRel membuktikan secara presisi bahwa pemilihan semen dan baja oleh pengembang di awal adalah pemicu utama transaksi bernilai miliaran rupiah.

#### Diagram Interaksi Aliran Data

```
+---------------------------------------------------------------------------------------------------------+
|                                    END-TO-END TELEMETRY FLOW                                            |
+---------------------------------------------------------------------------------------------------------+
    Developer CLI             GitHub API Gateway             Docs Site               Auth / Billing
    [cli.telemetry]           [webhook.events]           [docs.tracker]             [app.database]
           |                          |                         |                          |
           |-- 1. Heartbeat Event --> |                         |                          |
           |   (cli_uuid, arch)       |                         |                          |
           |                          |-- 2. Star/Fork Event -> |                          |
           |                          |   (gh_handle, repo)     |                          |
           |                          |                         |-- 3. Read Deep Dive ---> |
           |                          |                         |   (anonymous_cookie_id)  |
           |                          |                         |                          |
           |                          |                         |                          |-- 4. Sign Up (Email)
           |                          |                         |                          |   (user_id, email)
           |                          |                         |                          |
           v                          v                         v                          v
    +-------------------------------------------------------------------------------------------------+
    |                                FastAPI High-Throughput Edge Ingester                            |
    |               [HMAC Validation] -> [Schema Conformance] -> [Kafka Producer]                     |
    +-------------------------------------------------------------------------------------------------+
                                                     |
                                                     v Kafka Topic: "devrel.events.ingested"
    +-------------------------------------------------------------------------------------------------+
    |                                   ClickHouse Real-Time Store                                    |
    |  - events_raw (Kafka Engine Table)                                                              |
    |  - events_stream (Materialized View -> ReplacingMergeTree)                                      |
    +-------------------------------------------------------------------------------------------------+
                                                     |
                                                     v dbt Core Job (Hourly Scheduled)
    +-------------------------------------------------------------------------------------------------+
    |                              Attribution & Identity DAG Operations                              |
    |                                                                                                 |
    |   [Stitch Aliases] ------------> [Compute Path-to-Conversion] -------> [Markov Attribution DAG] |
    |   gh_handle + cookie + user_id   cli -> docs -> fork -> paid           Weights per Interaction  |
    +-------------------------------------------------------------------------------------------------+
                                                     |
                                                     v Reverse ETL / Analytical BI
    +-------------------------------------------------------------------------------------------------+
    |                 Business Impact Dashboards (Metabase) & RevOps Pipeline (Salesforce)            |
    +-------------------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Perhitungan Markov Chain Attribution Weights di Python

Contoh berikut menunjukkan logika dasar estimasi bobot atribusi menggunakan pustaka aljabar linier:

```python
"""
markov_attribution_simple.py
Implementasi dasar algoritma Markov Chain Attribution untuk alur perjalanan DevRel.
"""

from collections import defaultdict
import numpy as np

# Jalur perjalanan pengembang: touchpoints diakhiri dengan status 'CONVERSION' atau 'DROP'
JOURNEYS = [
    ["docs_quickstart", "github_clone", "cli_login", "CONVERSION"],
    ["docs_quickstart", "community_discord", "DROP"],
    ["community_discord", "github_clone", "cli_login", "CONVERSION"],
    ["youtube_tutorial", "docs_quickstart", "github_clone", "CONVERSION"],
    ["youtube_tutorial", "DROP"],
    ["github_clone", "cli_login", "CONVERSION"],
]


def calculate_transition_matrix(journeys: list[list[str]]) -> tuple[dict, np.ndarray, list[str]]:
    # Dapatkan seluruh node unik
    states = sorted(list({state for journey in journeys for state in journey}))
    state_to_idx = {state: idx for idx, state in enumerate(states)}
    n_states = len(states)

    transition_counts = np.zeros((n_states, n_states), dtype=np.float64)

    for journey in journeys:
        for i in range(len(journey) - 1):
            src = state_to_idx[journey[i]]
            dst = state_to_idx[journey[i + 1]]
            transition_counts[src][dst] += 1.0

    # Normalisasi baris untuk mendapatkan probabilitas transisi
    transition_matrix = np.zeros((n_states, n_states), dtype=np.float64)
    for i in range(n_states):
        row_sum = np.sum(transition_counts[i])
        if row_sum > 0:
            transition_matrix[i] = transition_counts[i] / row_sum
        else:
            # Absorbing state (CONVERSION atau DROP)
            transition_matrix[i][i] = 1.0

    return state_to_idx, transition_matrix, states


def calculate_conversion_probability(matrix: np.ndarray, state_to_idx: dict, states: list[str]) -> float:
    """Menghitung probabilitas penyerapan konversi total menggunakan fundamental matrix."""
    conv_idx = state_to_idx["CONVERSION"]
    drop_idx = state_to_idx["DROP"]

    # Identifikasi transient states (bukan terminal)
    transient_states = [s for s in states if s not in ("CONVERSION", "DROP")]
    if not transient_states:
        return 0.0

    tr_indices = [state_to_idx[s] for s in transient_states]

    # Matriks Q: Transisi antar transient states
    Q = matrix[np.ix_(tr_indices, tr_indices)]

    # Matriks R: Transisi dari transient states ke absorbing states (CONVERSION, DROP)
    abs_indices = [conv_idx, drop_idx]
    R = matrix[np.ix_(tr_indices, abs_indices)]

    # Fundamental Matrix N = (I - Q)^(-1)
    I = np.eye(len(tr_indices))
    try:
        N = np.linalg.inv(I - Q)
    except np.linalg.LinAlgError:
        return 0.0

    # Matriks Penyerapan B = N * R
    B = np.dot(N, R)

    # Probabilitas rata-rata mencapai CONVERSION dari state awal mana pun
    # Mengasumsikan probabilitas masuk seragam untuk tiap state awal transient
    prob_conv_from_start = np.mean(B[:, 0])
    return float(prob_conv_from_start)


def compute_markov_removal_effects(journeys: list[list[str]]) -> dict[str, float]:
    state_to_idx, base_matrix, states = calculate_transition_matrix(journeys)
    base_conv_prob = calculate_conversion_probability(base_matrix, state_to_idx, states)

    removal_effects = {}
    transient_states = [s for s in states if s not in ("CONVERSION", "DROP")]

    for target_state in transient_states:
        # Buat graf modifikasi dengan menghapus target_state (menjadikannya lead-to-DROP)
        modified_journeys = []
        for journey in journeys:
            if target_state in journey:
                # Potong perjalanan hingga titik sebelum target, diarahkan ke DROP
                idx = journey.index(target_state)
                trimmed = journey[:idx] + ["DROP"] if idx > 0 else ["DROP"]
                modified_journeys.append(trimmed)
            else:
                modified_journeys.append(journey)

        m_idx, m_mat, m_states = calculate_transition_matrix(modified_journeys)
        mod_conv_prob = calculate_conversion_probability(m_mat, m_idx, m_states)

        # Removal Effect = 1 - (Conversion prob after removal / Base conversion prob)
        effect = 1.0 - (mod_conv_prob / base_conv_prob if base_conv_prob > 0 else 0)
        removal_effects[target_state] = max(0.0, effect)

    total_effect = sum(removal_effects.values())
    if total_effect == 0:
        return {k: 0.0 for k in removal_effects}

    # Normalisasi bobot
    return {k: round(v / total_effect, 4) for k, v in removal_effects.items()}


if __name__ == "__main__":
    weights = compute_markov_removal_effects(JOURNEYS)
    print("Markov Attribution Weights per DevRel Touchpoint:")
    for channel, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        print(f" - {channel:<20}: {weight * 100:.2f}%")
```

---

#### 7.2. Practical Example: Production-Grade Telemetry Webhook Ingestor & ClickHouse Target

Berikut adalah implementasi sistem ingestion edge menggunakan FastAPI, Kafka Producer dengan schema conformance, dan model tabel ClickHouse untuk resolusi data analytical.

##### Bagian A: Ingestion Service (`ingest_edge_service.py`)

```python
"""
ingest_edge_service.py
Layanan Edge Ingestor DevRel Telemetry dengan validasi tanda tangan HMAC,
schema validation, dan partisi streaming berkinerja tinggi ke Apache Kafka.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import os
from typing import Any, Literal
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from confluent_kafka import Producer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DevRelTelemetryIngest")

WEBHOOK_SECRET = os.getenv("DEVREL_WEBHOOK_SECRET", "super-secure-production-hmac-key")
KAFKA_BROKERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = "telemetry.devrel.raw"

app = FastAPI(
    title="DevRel Telemetry Engine API",
    version="1.0.0",
    docs_url=None,  # Dinonaktifkan di edge public demi security hardening
)

# Inisialisasi thread-safe Kafka Producer
kafka_producer = Producer({
    "bootstrap.servers": KAFKA_BROKERS,
    "acks": "all",
    "enable.idempotence": True,
    "compression.type": "zstd",
    "retries": 5,
})


class TelemetryEventPayload(BaseModel):
    event_id: str = Field(..., description="UUID v4 unik dari pengirim event")
    timestamp: datetime = Field(..., description="Waktu kejadian dalam format ISO8601 UTC")
    source: Literal["docs", "cli", "github", "discord", "developer_portal"]
    action: str = Field(..., example="docs_quickstart_run")
    actor_aliases: dict[str, str] = Field(
        ...,
        description="Peta pengenal identitas, cth: {'github_handle': 'xyz', 'client_uuid': 'abc'}",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


def verify_hmac_signature(payload_bytes: bytes, signature_header: str | None) -> bool:
    if not signature_header:
        return False
    try:
        algo, signature = signature_header.split("=", 1)
        if algo != "sha256":
            return False
        expected_signature = hmac.new(
            WEBHOOK_SECRET.encode("utf-8"),
            msg=payload_bytes,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except Exception as exc:
        logger.error(f"Gagal memvalidasi HMAC: {exc}")
        return False


def kafka_delivery_report(err, msg):
    if err is not None:
        logger.error(f"Gagal mengirim pesan ke Kafka: {err}")
    else:
        logger.debug(
            f"Event sukses dikirim ke {msg.topic()} partition [{msg.partition()}] offset {msg.offset()}"
        )


@app.post("/v1/telemetry/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(
    request: Request,
    x_devrel_signature: str | None = Header(None, alias="X-DevRel-Signature"),
):
    body_bytes = await request.body()

    # Validasi otentikasi webhook
    if not verify_hmac_signature(body_bytes, x_devrel_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Validasi otentikasi cryptographic signature gagal.",
        )

    try:
        raw_json = json.loads(body_bytes.decode("utf-8"))
        validated_event = TelemetryEventPayload(**raw_json)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Schema violation: {str(exc)}",
        )

    # Serialisasi terstandarisasi untuk Kafka
    partition_key = (
        validated_event.actor_aliases.get("github_handle")
        or validated_event.actor_aliases.get("client_uuid")
        or validated_event.actor_aliases.get("cookie_id")
        or validated_event.event_id
    )

    kafka_payload = {
        "event_id": validated_event.event_id,
        "source": validated_event.source,
        "action": validated_event.action,
        "emitted_at": validated_event.timestamp.astimezone(timezone.utc).isoformat(),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "actor_aliases": validated_event.actor_aliases,
        "metadata_json": json.dumps(validated_event.metadata),
    }

    try:
        kafka_producer.produce(
            topic=KAFKA_TOPIC,
            key=partition_key.encode("utf-8"),
            value=json.dumps(kafka_payload).encode("utf-8"),
            on_delivery=kafka_delivery_report,
        )
        kafka_producer.poll(0)
    except BufferError:
        logger.warning("Kafka Producer internal buffer penuh! Melakukan pembilasan paksa.")
        kafka_producer.flush()
        kafka_producer.produce(
            topic=KAFKA_TOPIC,
            key=partition_key.encode("utf-8"),
            value=json.dumps(kafka_payload).encode("utf-8"),
            on_delivery=kafka_delivery_report,
        )

    return {"status": "accepted", "event_id": validated_event.event_id}


@app.on_event("shutdown")
def shutdown_event():
    logger.info("Membilas antrean event Kafka producer...")
    kafka_producer.flush(timeout=10.0)
```

##### Bagian B: Skema Data Warehouse ClickHouse (`schema_clickhouse.sql`)

```sql
-- DDL ClickHouse untuk penampungan event telemetry DevRel dan Identity Resolution

CREATE DATABASE IF NOT EXISTS devrel_analytics;

USE devrel_analytics;

-- 1. Ingestion Table: Menerima streaming dari Kafka via ClickHouse Kafka Engine
CREATE TABLE IF NOT EXISTS devrel_analytics.events_kafka_inbound
(
    event_id String,
    source LowCardinality(String),
    action LowCardinality(String),
    emitted_at DateTime64(3, 'UTC'),
    ingested_at DateTime64(3, 'UTC'),
    actor_aliases Map(String, String),
    metadata_json String
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'localhost:9092',
         kafka_topic_list = 'telemetry.devrel.raw',
         kafka_group_name = 'ch_devrel_consumer_group',
         kafka_format = 'JSONEachRow',
         kafka_num_consumers = 2;

-- 2. Target Analytics Storage Table (ReplacingMergeTree untuk deduplikasi)
CREATE TABLE IF NOT EXISTS devrel_analytics.events_fact
(
    event_id UUID,
    event_date Date DEFAULT toDate(emitted_at),
    source LowCardinality(String),
    action LowCardinality(String),
    emitted_at DateTime64(3, 'UTC'),
    ingested_at DateTime64(3, 'UTC'),
    github_handle Nullable(String),
    client_uuid Nullable(String),
    cookie_id Nullable(String),
    workspace_id Nullable(String),
    metadata_json String
)
ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (source, action, emitted_at, event_id);

-- 3. Materialized View untuk Pipeline Ekstraksi Otomatis
CREATE MATERIALIZED VIEW IF NOT EXISTS devrel_analytics.mv_events_kafka_to_fact
TO devrel_analytics.events_fact AS
SELECT
    toUUID(event_id) AS event_id,
    toDate(emitted_at) AS event_date,
    source,
    action,
    emitted_at,
    ingested_at,
    nullIf(actor_aliases['github_handle'], '') AS github_handle,
    nullIf(actor_aliases['client_uuid'], '') AS client_uuid,
    nullIf(actor_aliases['cookie_id'], '') AS cookie_id,
    nullIf(actor_aliases['workspace_id'], '') AS workspace_id,
    metadata_json
FROM devrel_analytics.events_kafka_inbound;

-- 4. Identity Graph Resolution: Tabel Canonical Stitching
CREATE TABLE IF NOT EXISTS devrel_analytics.developer_identity_graph
(
    alias_type LowCardinality(String),
    alias_value String,
    canonical_dev_id UUID,
    confidence_score Float32,
    first_associated_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (alias_type, alias_value);
```

##### Bagian C: Transformasi dbt Identity Resolution & Attribution (`devrel_mta_model.sql`)

```sql
-- models/attribution/devrel_w_shaped_attribution.sql
-- Model transformasi dbt untuk menghitung atribusi W-Shaped (40% First Touch, 40% Lead Creation, 20% Middle Touchpoints)

WITH touchpoints AS (
    SELECT
        ef.event_id,
        coalesce(dig.canonical_dev_id, ef.event_id) AS canonical_dev_id,
        ef.source,
        ef.action,
        ef.emitted_at,
        ef.workspace_id,
        ROW_NUMBER() OVER (
            PARTITION BY coalesce(dig.canonical_dev_id, ef.event_id) 
            ORDER BY ef.emitted_at ASC
        ) AS touchpoint_asc_rank,
        COUNT(*) OVER (
            PARTITION BY coalesce(dig.canonical_dev_id, ef.event_id)
        ) AS total_touchpoints
    FROM {{ ref('events_fact') }} ef
    LEFT JOIN {{ ref('developer_identity_graph') }} dig
        ON (ef.github_handle = dig.alias_value AND dig.alias_type = 'github_handle')
        OR (ef.cookie_id = dig.alias_value AND dig.alias_type = 'cookie_id')
        OR (ef.client_uuid = dig.alias_value AND dig.alias_type = 'client_uuid')
),

conversions AS (
    SELECT
        workspace_id,
        canonical_dev_id,
        deal_value_usd,
        converted_at
    FROM {{ ref('fct_enterprise_api_contracts') }}
),

journey_stitching AS (
    SELECT
        t.event_id,
        t.canonical_dev_id,
        t.source,
        t.action,
        t.emitted_at,
        c.workspace_id,
        c.deal_value_usd,
        t.touchpoint_asc_rank,
        t.total_touchpoints,
        CASE
            -- Single-touch journey
            WHEN t.total_touchpoints = 1 THEN 1.0
            
            -- Two-touch journey (50% First, 50% Last)
            WHEN t.total_touchpoints = 2 THEN 0.50
            
            -- W-Shaped (>=3 touches): 40% First Touch, 40% Conversion Touch, 20% dibagi rata ke Mid Touches
            WHEN t.touchpoint_asc_rank = 1 THEN 0.40
            WHEN t.touchpoint_asc_rank = t.total_touchpoints THEN 0.40
            ELSE 0.20 / (t.total_touchpoints - 2)
        END AS attribution_weight
    FROM touchpoints t
    INNER JOIN conversions c
        ON t.canonical_dev_id = c.canonical_dev_id
       AND t.emitted_at <= c.converted_at
)

SELECT
    event_id,
    canonical_dev_id,
    workspace_id,
    source,
    action,
    emitted_at,
    deal_value_usd,
    attribution_weight,
    ROUND(deal_value_usd * attribution_weight, 2) AS attributed_revenue_usd
FROM journey_stitching
ORDER BY canonical_dev_id, emitted_at ASC;
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: "CognitoFlow AI" – Platform Infrastruktur LLM Enterprise
- **Skala**: 450.000 developer bulanan, 1.200 enterprise customer, 120 juta panggilan API/hari.
- **Masalah Bisnis**: Manajemen mengalokasikan anggaran $3.5M/tahun untuk DevRel (tim Advocate yang mengisi konferensi, mengelola 80 repository *quickstart/agent-templates*, dan mengelola komunitas Discord 50.000 anggota). Namun, CFO menuntut validasi: Berapa banyak dari $40M Annual Recurring Revenue (ARR) yang dipengaruhi langsung oleh artefak open-source dan program edukasi DevRel?
- **Kegagalan Solusi Awal**: Tim pemasaran menggunakan Google Analytics UTM tags. Hasilnya menunjukkan 92% enterprise leads datang via *Direct Navigation* atau *Organic Search* pada domain login, sehingga kontribusi DevRel tercatat hanya < 2%.

#### Solusi Arsitektur DevRel Attribution Engine:
1. **Pemasangan Telemetry Non-Intrusif**:
   - Menambahkan event emitter OpenTelemetry berbobot ringan di official Python/TypeScript SDK yang mengirimkan hash anonim mesin pengembang dan ID template repositori saat `init()` dipanggil.
   - Pemasangan webhook GitHub pada 80 repo organisasi CognitoFlow yang menangkap interaksi `fork`, `star`, dan `issue_comment`.
   - Mengintegrasikan CLI auth callback yang memetakan identifier instalasi CLI lokal dengan identitas platform CognitoFlow via OAuth 2.0 PKCE.
2. **Pipeline Ingestion & Identity Stitching**:
   - Memproses 4.000 event/detik menggunakan Apache Redpanda -> ClickHouse.
   - Membuat Graph Database (Neo4j) berbobot ringan yang dijalankan secara batch tiap 6 jam untuk menyatukan alias: `{github_handle, corporate_email_domain, local_cli_id, web_cookie}`.
3. **Hasil yang Terverifikasi (Business Impact)**:
   - **Validasi Nilai DevRel**: Terbukti bahwa 64% akun Enterprise yang membayar kontrak $\ge \$50.000$/tahun memiliki setidaknya 3 sentuhan (*touchpoints*) dengan artefak DevRel (misal: kloning template RAG atau interaksi di GitHub Discussions) 60 hari sebelum tim sales mereka membuat tiket kesepakatan (*opportunity*).
   - **Sales Acceleration**: Siklus transaksi (*Sales cycle velocity*) untuk pengembang yang sebelumnya mengkloning repo GitHub DevRel tercatat 43% lebih singkat (rata-rata 18 hari vs 32 hari untuk cold sales outbound).
   - **Reallocation of Budget**: Tim menghentikan sponsor di 15 konferensi umum berbiaya tinggi dan mengalihkan 60% anggaran ke dokumentasi interaktif dan template repositori kode setelah analisis Markov membuktikan *Removal Effect* tertinggi berasal dari template repositori agen mandiri.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | Pendekatan Deterministik (Strict Auth) | Pendekatan Heuristik/Probabilistik | Pendekatan Algoritmik Lanjutan (Markov/Shapley) |
| :--- | :--- | :--- | :--- |
| **Akurasi Atribusi** | 99.9% (Hampir absolut, tidak ada false-positives). | 70% - 85% (Rentan distorsi jika banyak developer berbagi IP proxy korporat). | Tinggi secara matematis untuk mengukur kontribusi saluran agregat; tidak cocok untuk metrik level individu. |
| **Cakupan Data (Coverage)** | Rendah (Hanya 15% - 25% pengembang yang mengautentikasi seluruh tools). | Tinggi (Menjangkau 70%+ developer yang bersifat anonim). | Menengah-Tinggi (Berbasis seluruh historical path yang terhubung ke konversi). |
| **Beban Komputasi** | Sangat Ringan (Pencarian relasional SQL standar sederhana). | Sedang (Membutuhkan window time-joins dan normalisasi alamat IP/subnet). | Berat (Inversi matriks orde tinggi $O(N^3)$, membutuhkan data warehouse berspesifikasi tinggi). |
| **Biaya Infrastruktur** | Sangat Rendah. | Sedang (Trafik log ClickHouse besar). | Tinggi (Komputasi dbt/Python secara rutin pada jutaan alur data). |
| **Latency Metrik** | Real-time / Sub-detik. | Batch (Hourly / Daily windowing). | Batch (Harian / Mingguan karena windowing yang kompleks). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: "The GitHub Star Fallacy" (Vanity Metrics Obsession)
- *Gejala*: Tim DevRel melaporkan peningkatan 5.000 GitHub Stars dalam satu kuartal, namun tingkat registrasi API dan pendapatan stagnan.
- *Akar Masalah*: Bot farm, akun semu, dan aksi impulsif developer tanpa intent adopsi kode riil.
- *Solusi Perbaikan*: Ganti KPI primer dengan **Repository Clone-to-Token-Creation Rate** dan **Active CLI Sessions**. Berikan bobot 0.01 pada bintang GitHub dalam model atribusi, tetapi berikan bobot 0.40 pada commit nyata atau penggunaan SDK di lingkungan lokal.

#### Kesalahan 2: Pelanggaran Privasi Pengembang (PII Spillage)
- *Gejala*: Menyimpan plain-text alamat IP, data clipboard CLI, atau private git remote URL ke data warehouse, memicu teguran kepatuhan regulasi privasi (GDPR).
- *Solusi Perbaikan*: 
  - Terapkan mekanisme cryptographic one-way hashing dengan rotasi garam harian (*daily salted hash*) sebelum mengirimkan data ke Kafka:
    ```python
    hashed_ip = hashlib.sha256((client_ip + DAILY_SALT).encode()).hexdigest()
    ```
  - CLI hanya boleh mengirimkan identifier berbasis UUID yang dihasilkan secara acak saat instalasi, bukan data identitas lingkungan seperti hostname personal atau path direktori pengguna (`/Users/nama_lengkap/...`).

#### Kesalahan 3: Missing Idempotency pada Webhook Receivers
- *Gejala*: Pengembang melakukan fork/star berulang kali atau webhook GitHub mengirimkan pengiriman ulang (*redelivery*), mengakibatkan lonjakan metrik hingga 300%.
- *Solusi Perbaikan*: Terapkan deduplikasi berbasis Redis TTL Cache di edge layer menggunakan header `X-GitHub-Delivery` ID, dikombinasikan dengan ClickHouse `ReplacingMergeTree` engine yang diindeks berdasarkan `event_id`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Security**: Seluruh webhook receiver memvalidasi tanda tangan kriptografis HMAC SHA-256 dengan mekanisme *constant-time comparison* (`hmac.compare_digest`).
- [ ] **Data Minimization**: Menyensor parameter kueri URL docs yang mengandung token otorisasi, access key, atau identitas pribadi sebelum diarahkan ke pipeline analisis.
- [ ] **Schema Conformance**: Menggunakan validasi skema runtime (Pydantic / Protobuf / Confluent Schema Registry) di gateway layer untuk mencegah *poison pill events* merusak antrean Kafka.
- [ ] **Idempotent Ingestion**: Memastikan pengiriman Kafka menggunakan `enable.idempotence=true` dan partition key terdistribusi merata untuk menghindari data skew di broker.
- [ ] **Data Warehousing Partitioning**: Tabel ClickHouse dipartisi berdasarkan bulan `toYYYYMM(event_date)` dengan `ORDER BY (source, action, emitted_at, event_id)` demi optimasi *columnar data pruning*.
- [ ] **Audit Trail**: Menyimpan log raw audit selama minimal 30 hari dalam format terkompresi (zstd) di S3/GCS Object Storage sebelum dihapus oleh siklus retensi data.
- [ ] **Attribution Windows**: Menetapkan batas atribusi (*lookback window*) yang realistis untuk pengembang (standar industri: 90 hari untuk adopsi API open-source, 180 hari untuk kontrak API enterprise).

---

### 12. Hands-on Practice

Struktur direktori kerja:
```
hands-on/m02/
├── docker-compose.yml
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py
│   └── config.py
├── scripts/
│   ├── simulate_traffic.py
│   └── calculate_attribution.py
└── sql/
    └── clickhouse_init.sql
```

#### Langkah 1: Siapkan Lingkungan Pengujian
Buat file `docker-compose.yml` di direktori `hands-on/m02/`:

```yaml
version: '3.8'

services:
  redpanda:
    image: docker.redpanda.com/redpandadata/redpanda:v23.3.10
    container_name: devrel-redpanda
    command:
      - redpanda start
      - --smp 1
      - --memory 1G
      - --overprovisioned
      - --kafka-addr PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr PLAINTEXT://localhost:9092
    ports:
      - "9092:9092"

  clickhouse:
    image: clickhouse/clickhouse-server:24.3
    container_name: devrel-clickhouse
    ports:
      - "8123:8123"
      - "9000:9000"
    environment:
      CLICKHOUSE_DB: devrel_analytics
      CLICKHOUSE_USER: devrel_admin
      CLICKHOUSE_PASSWORD: devrel_secure_password
    ulimits:
      nofile:
        soft: 262144
        hard: 262144
```

#### Langkah 2: Jalankan Kontainer dan Inisialisasi Database
1. Eksekusi perutean kontainer:
   ```bash
   cd hands-on/m02/
   docker compose up -d
   ```
2. Pastikan port 9092 (Redpanda/Kafka) dan 8123 (ClickHouse HTTP) aktif.
3. Jalankan inisialisasi skema SQL:
   ```bash
   docker exec -i devrel-clickhouse clickhouse-client \
     --user devrel_admin \
     --password devrel_secure_password \
     --multiquery < sql/clickhouse_init.sql
   ```

#### Langkah 3: Jalankan Layanan Ingestion & Simulasi Data
1. Install dependensi:
   ```bash
   pip install fastapi uvicorn confluent-kafka clickhouse-connect pydantic
   ```
2. Jalankan server FastAPI:
   ```bash
   export DEVREL_WEBHOOK_SECRET="test-secret-key-1234"
   uvicorn app.main:app --port 8000 --reload
   ```
3. Buka terminal baru dan jalankan simulator payload webhook untuk memverifikasi penyerapan stream:
   ```bash
   python scripts/simulate_traffic.py
   ```

---

### 13. Exercise

#### Level 1 (Easy) - First-Touch SQL Attribution Extraction
Tulis kueri SQL di ClickHouse untuk mengambil 10 sumber pertama (*first-touch source*) yang paling sering memicu pendaftaran pengembang baru dalam 30 hari terakhir.
- *Input*: Tabel `devrel_analytics.events_fact`
- *Ekspektasi Output*: Kolom `first_touch_source`, `conversions_count`, terurut berdasarkan volume tertinggi.

#### Level 2 (Medium) - GitHub Webhook Signature Interceptor Middleware
Kembangkan modul middleware Python ASGI yang dapat disisipkan ke FastAPI untuk secara otomatis memotong (*intercept*) setiap webhook GitHub inbound, memvalidasi header `X-Hub-Signature-256`, dan menolak request dengan HTTP 403 Forbidden secara asinkron tanpa memblokir *event loop* aplikasi.

#### Level 3 (Hard) - Custom Graph Stitching Engine
Rancang algoritma rekursif atau operasi SQL (menggunakan Graph-traversal / Recursive CTE) yang menerima pasangan alias `(alias_a, alias_b)` dari tabel stream yang terfragmentasi, dan menghasilkan tabel lookup deterministik yang memetakan seluruh variasi alias yang memiliki keterkaitan relasional tidak langsung ke satu `canonical_developer_id` yang sama. Tangani dependensi siklik (cth: A terhubung ke B, B terhubung ke C, C terhubung kembali ke A).

---

### 14. Challenge

#### Studi Kasus Kompleks: "The Dark Social & Ephemeral VPN Developer Paradox"

**Skenario**:
Perusahaan Anda menyediakan infrastruktur *vector database* terdistribusi. Sembilan puluh persen pengembang enterprise yang mengevaluasi produk Anda mematuhi kebijakan keamanan korporat yang ketat:
1. Mereka menggunakan VPN perusahaan dengan IP yang berubah-ubah (*shared egress gateway* digunakan oleh 15.000 karyawan).
2. Mereka menelusuri dokumentasi teknis API Anda melalui peramban yang memblokir penyimpanan cookie pihak pertama lebih dari 24 jam.
3. Mereka melakukan kloning kode template repositori menggunakan akun personal GitHub anonim di rumah, tetapi mendaftar akun produksi berbayar menggunakan single sign-on (SSO) email korporat Google Workspace/Okta kantor.
4. Tim DevRel Anda menyelenggarakan workshop tatap muka di mana para pengembang ini hadir tanpa registrasi email korporat (hanya mengisi presensi dengan akun Twitter/LinkedIn).

**Tugas Arsitektural**:
Rancang dokumen arsitektur dan cetak biru pipeline data yang mampu menyelesaikan keterputusan data (*attribution black hole*) ini secara etis dan akurat tanpa melanggar prinsip Zero-Trust Security maupun regulasi privasi data:
- Tentukan mekanisme penautan identitas (*stitching telemetry*) yang digunakan saat pengembang berpindah dari lingkungan personal (rumah/GitHub) ke lingkungan kantor (VPN/SSO email).
- Formulasikan strategi integrasi titik singgung luring (*offline meetup/workshop touchpoint*) ke dalam pipeline digital event lakehouse.
- Jelaskan batas toleransi margin eror model atribusi Anda dan sajikan formula penyesuaian bobot (*confidence score decay*) saat atribut probabilistik digunakan.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)

1. **Apa perbedaan mendasar antara metrik Vanity dan metrik Impact dalam konteks Developer Relations?**
   - A. Metrik Vanity mengukur transaksi keuangan langsung; metrik Impact mengukur keterlibatan media sosial.
   - B. Metrik Vanity berfokus pada volume permukaan yang mudah dimanipulasi (cth: GitHub Stars); metrik Impact berfokus pada adopsi produk yang berkontribusi pada pendapatan atau konversi teknis (cth: Token consumption, CLI logins).
   - C. Metrik Vanity hanya digunakan oleh tim engineering; metrik Impact hanya digunakan oleh tim PR.
   - D. Metrik Vanity memerlukan tracking berbasis database analitik; metrik Impact cukup dipantau lewat spreadsheet.
   *(Jawaban: B — Metrik vanity mengukur popularitas permukaan yang tidak menjamin keberlanjutan bisnis, sedangkan metrik impact membuktikan adopsi fungsional produk).*

2. **Mengapa algoritma Last-Touch Attribution dianggap tidak memadai untuk mengevaluasi efektivitas DevRel?**
   - A. Karena Last-Touch Attribution membutuhkan kapasitas penyimpanan database yang terlalu besar.
   - B. Karena Last-Touch Attribution mengabaikan touchpoint awal dan edukatif penting (seperti dokumentasi, repositori contoh, workshop) dan memberikan 100% kredit pada langkah akhir seperti pendaftaran form.
   - C. Karena Last-Touch Attribution tidak kompatibel dengan protokol HTTP POST.
   - D. Karena Last-Touch Attribution hanya bekerja pada perangkat mobile.
   *(Jawaban: B — DevRel bekerja di tahap edukasi teknis awal hingga menengah; model last-touch memberikan bias tidak adil ke event transaksional di akhir funnel).*

3. **Fungsi utama header `X-Hub-Signature-256` pada payload webhook GitHub adalah...**
   - A. Mengompresi payload webhook menggunakan gzip.
   - B. Mengenkripsi isi payload agar tidak bisa dibaca oleh proxy jaringan.
   - C. Memungkinkan penerima memverifikasi bahwa payload dikirimkan secara autentik oleh GitHub dan tidak dimodifikasi oleh pihak ketiga (Integritas & Autentikasi).
   - D. Menyimpan identitas IP pengembang yang melakukan trigger action.
   *(Jawaban: C — Header tersebut menyimpan signature HMAC-SHA256 untuk memverifikasi autentisitas pengirim menggunakan shared secret).*

4. **Metrik TTFW dalam siklus aktivasi developer merupakan singkatan dari...**
   - A. Time to Full Workspace.
   - B. Total Terminal Function Weight.
   - C. Time to First "Hello World".
   - D. Target Telemetry Framework Window.
   *(Jawaban: C — Time to First "Hello World" mengukur durasi yang dibutuhkan pengembang dari menemukan platform hingga berhasil mengeksekusi integrasi kode pertama).*

5. **Karakteristik utama mesin database ClickHouse yang menjadikannya pilihan ideal untuk developer telemetry storage adalah...**
   - A. Penyimpanan berorientasi baris (row-oriented) dengan transaksi ACID multi-dokumen.
   - B. Arsitektur berorientasi kolom (column-oriented) yang dioptimalkan untuk agregasi data analitik bervolume masif dengan latensi sub-detik.
   - C. Dukungan native untuk graph querying setara Neo4j tanpa indeks skema.
   - D. Sistem database terdistribusi in-memory murni yang tidak menulis data ke disk.
   *(Jawaban: B — ClickHouse adalah Columnar OLAP DBMS yang dirancang untuk analisis agregasi cepat pada miliaran baris event telemetry).*

---

#### Bagian 2: Intermediate (5 Soal)

6. **Dalam pemodelan Markov Chain Attribution, bagaimana nilai kontribusi suatu touchpoint dihitung?**
   - A. Menghitung jumlah klik langsung pada tautan touchpoint tersebut dibagi total kunjungan web.
   - B. Menghitung selisih probabilitas konversi graf normal dengan probabilitas konversi saat touchpoint tersebut dihapus dari graf (Removal Effect).
   - C. Membagi rata nilai konversi ke semua touchpoint yang aktif dalam 24 jam terakhir.
   - D. Mengalikan jumlah impresi touchpoint dengan rata-rata nilai transaksi kontrak enterprise.
   *(Jawaban: B — Removal Effect heuristic mengukur degradasi sistem konversi ketika suatu node diisolasi/dihapus).*

7. **Bagaimana cara mencegah kebocoran PII (Personally Identifiable Information) saat mengumpulkan telemetry CLI dari workstation lokal pengembang?**
   - A. Mengirimkan seluruh log terminal pengembang secara utuh untuk dianalisis di cloud backend.
   - B. Menghasilkan client-side UUID acak saat proses instalasi dan melakukan one-way salted hashing pada data sensitif sebelum transmisi.
   - C. Menyimpan IP pengembang di tabel terbuka tanpa enkripsi.
   - D. Mengharuskan pengembang memasukkan nomor kartu identitas sebelum menjalankan CLI.
   *(Jawaban: B — Prinsip data minimization dan pseudonymization mewajibkan penggunaan UUID acak dan hashing non-reversible).*

8. **Tabel ClickHouse dengan engine `ReplacingMergeTree` menyelesaikan masalah apa dalam pipeline ingestion Kafka?**
   - A. Mempercepat proses deserialisasi format JSON ke Avro.
   - B. Melakukan deduplikasi event secara otomatis berdasarkan primary key saat proses merge background berlangsung.
   - C. Mengonversi data numerik menjadi representasi grafik secara real-time.
   - D. Menghapus data secara otomatis setelah 10 menit tanpa TTL setting.
   *(Jawaban: B — ReplacingMergeTree menghapus baris duplikat yang memiliki kunci ordering sama pada siklus merge engine).*

9. **Model atribusi W-Shaped memberikan alokasi bobot persentase terbesar pada tiga touchpoint utama, yaitu...**
   - A. First Touch, Mid-funnel Opportunity Creation Touch, dan Final Closed-Won Deal Touch.
   - B. Social Media Impression, Website Visit, dan Newsletter Subscription.
   - C. GitHub Star, Discord Message, dan Forum Upvote.
   - D. YouTube Video View, Documentation Browse, dan Support Ticket Creation.
   *(Jawaban: A — W-shaped attribution mendistribusikan bobot utama (biasanya 40-20-40 atau variasi serupa) pada sentuhan pertama, pembuatan peluang teknis/lead, dan penutupan transaksi).*

10. **Apa risiko teknis utama mengandalkan IP korporat untuk menghubungkan identitas pengembang (*identity stitching*) secara probabilistik?**
    - A. IP Address selalu bernilai unik untuk tiap laptop di seluruh dunia.
    - B. Egress IP gateway korporat dapat digunakan bersama oleh ribuan pengguna di perusahaan yang sama, memicu penggabungan data developer yang tidak saling berkaitan (*over-stitching/false-positive match*).
    - C. Browser melarang protokol HTTP mengirimkan paket data melalui proxy perusahaan.
    - D. IP Address selalu berubah setiap 5 detik secara native pada sistem operasi modern.
    *(Jawaban: B — Shared NAT/corporate egress proxies menyebabkan ribuan perangkat di balik satu organisasi memiliki IP publik yang identik).*

---

#### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario Kasus A**:
    Platform API AI Anda mendeteksi lonjakan tiba-tiba sebesar 25.000 GitHub Stars dalam 48 jam pada repositori open-source resmi setelah Advocate Anda berbicara di konferensi. Namun, metrik registrasi dashboard developer dan pembuatan API Token di Kafka tidak menunjukkan kenaikan deviasi yang signifikan ($\le 1.2\%$).
    - *Analisis*: Apa kemungkinan akar masalah teknis ini, dan langkah mitigasi apa yang harus diterapkan pada pipeline atribusi DevRel?
    - *Solusi & Jawaban*: Fenomena ini mengindikasikan adanya manipulasi *sybil attack*, *bot farm campaign*, atau aksi kosmetik dengan intent adopsi rendah. Pipeline atribusi harus menerapkan filter anomaly detection:
      1. Menghitung rasio *Star-to-Active-Fork* dan *Star-to-Commit/Clone*.
      2. Mengabaikan akun GitHub yang baru dibuat ($< 7\text{ hari}$) atau tidak memiliki aktivitas riil di graf identitas.
      3. Menghapus bobot metrik Star dari penentuan KPI keberhasilan DevRel dan memfokuskan dashboard pada metrik *SDK Invocations* dan *API Keys with Active Traffic*.

12. **Skenario Kasus B**:
    Layanan webhook receiver FastAPI Anda di edge cluster mengalami penurunan performa drastis (*high latency tail* p99 naik dari 45ms ke 12 detik) dan menghasilkan respons HTTP 503 saat tim DevRel meluncurkan kampanye hackathon global secara langsung. Log menunjukkan antrean worker FastAPI kehabisan memori.
    - *Analisis*: Mengapa sistem mengalami kegagalan ini dan bagaimana rekayasa ulang arsitektur penyerapannya?
    - *Solusi & Jawaban*: Layanan edge melakukan komputasi berat secara synchronous (seperti parsing mendalam, penulisan ke database relasional, atau pemanggilan verifikasi blocking) sebelum merespons HTTP request.
      *Rekayasa Ulang*:
      1. Pisahkan layer ingress: Endpoint hanya memvalidasi HMAC signature secara in-memory, lalu segera melemparkan payload utuh ke Kafka/Redpanda topic menggunakan producer async non-blocking, kemudian langsung mengembalikan `HTTP 202 Accepted`.
      2. Pindahkan seluruh parsing metadata, validasi skema kompleks, dan identity graph stitching ke worker asynchronous di belakang antrean buffer Kafka.
      3. Terapkan konfigurasi backpressure dan auto-scaling horizontal pada Ingress pods berbasis target penggunaan memori/CPU.

13. **Skenario Kasus C**:
    Chief Revenue Officer (CRO) menuduh data atribusi tim DevRel tidak valid karena model dbt MTA mencatat bahwa $1.2M ARR dari satu transaksi Enterprise Fortune 500 diatribusikan 40% ke sebuah postingan blog teknis dan sample code yang dibuat Developer Advocate setahun yang lalu.
    - *Analisis*: Bagaimana Anda memvalidasi atau merevisi temuan ini secara teknis dan arsitektural?
    - *Solusi & Jawaban*: 
      1. Periksa batas lookback window model. Jika jendela atribusi disetel *unbounded* (tanpa batas waktu), interaksi usang akan tetap menyerap kredit pendapatan secara tidak proporsional.
      2. Terapkan *Time-Decay Function* atau *Half-Life Decay Parameter* pada model atribusi (misalnya menggunakan fungsi peluruhan eksponensial $W(t) = 2^{-t / \lambda}$ dengan half-life 60 atau 90 hari).
      3. Validasi jejak kanonikal: Pastikan bahwa insinyur enterprise yang membaca blog tersebut benar-benar orang yang sama atau berada dalam tim engineering yang sama dengan yang menerbitkan Production API Key untuk kontrak enterprise tersebut via resolusi email domain korporat, bukan kebetulan trafik browsing dari unit bisnis non-teknis.

---

### 16. Summary

Mengukur dampak bisnis Developer Relations (DevRel) secara presisi membutuhkan transformasi fundamental dari sekadar mengumpulkan *vanity metrics* menuju implementasi infrastruktur data terdistribusi yang komprehensif. Perjalanan pengembang modern bersifat non-linear, sering kali diawali dengan eksplorasi kode secara anonim sebelum bertransisi menjadi pengguna berbayar di tingkat enterprise.

Melalui pembangunan **Developer Identity Graph**, pemrosesan event streaming latensi rendah berbasis **Kafka dan ClickHouse**, serta pemodelan atribusi mutakhir (**Markov Chain Removal Effects** dan **W-Shaped Attribution**), tim data engineering mampu menghubungkan setiap baris kode, dokumentasi teknis, dan advokasi komunitas secara langsung dengan metrik pertumbuhan bisnis inti: *Product-Qualified Leads (PQL)*, pemanfaatan kapasitas API, dan penutupan nilai kontrak *Enterprise Annual Recurring Revenue (ARR)*. Hasilnya adalah pembuktian nilai investasi DevRel yang terukur, dapat diaudit, dan terlindungi secara regulasi privasi.