# Bab 09: Enterprise Monitoring, Log Analysis & Algorithmic Diagnostics
## Modul 01: Real-Time Edge Log Streaming, Bot Verification Engine & Crawl Telemetry Architecture

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang Arsitektur Ingesti Edge Log Skala Enterprise**: Mengonfigurasi pipeline penyerapan data log streaming dari CDN (Cloudflare/Fastly/Akamai) ke message broker berthroughput tinggi dengan latensi p99 $< 2.5$ detik.
- **Mengimplementasikan Bot Verification Engine**: Mengembangkan subsistem verifikasi bot mesin telusur secara asinkron menggunakan teknik validasi *Double Reverse DNS Lookup* (rDNS + Forward DNS) berkinerja tinggi dengan multi-tiered in-memory caching.
- **Mengisolasi Anomali Crawl Budget & Status Code**: Membangun algoritma deteksi statistik (CUSUM & Adaptive Moving Average) untuk mengidentifikasi lonjakan respons HTTP 429/5xx, pergeseran pola *crawling* direktori, dan *soft 404* secara real-time.
- **Mendiagnosis Volatilitas Algoritmik vs Regresi Teknis**: Memisahkan korelasi penurunan trafik organik akibat *search engine core update* dari degradasi infrastruktur melalui perbandingan deret waktu (*time-series cross-correlation*) antara log *crawl bot* dan metrik *Core Web Vitals*.

---

### 2. Concept Overview

Sistem diagnostik SEO enterprise beroperasi pada premis dasar: **Log server adalah representasi faktual tunggal dari interaksi mesin pencari dengan platform web.** Berbeda dari data Google Search Console yang mengalami agregasi, *sampling*, dan latensi 48–72 jam, *edge access logs* mencatat setiap request HTTP/HTTPS secara deterministik.

```
       [ Edge Network / CDN ]
                 │
                 ▼ (Log Streaming / Syslog / S3 Chunk)
    [ Ingestion & Normalization Worker ]
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
[Spoofing Detection]  [Telemetry Aggregation]
(rDNS + FQDN Cache)   (ClickHouse / Time Series)
      │                     │
      └──────────┬──────────┘
                 ▼
    [Algorithmic Diagnostic Engine]
    (CUSUM / Z-Score Spike Detection)
```

#### Mental Model: Crawl-to-Index Pipeline Telemetry

1. **Discovery & Crawling (Edge Layer)**: Googlebot mengirim request HTTP. Pada tahap ini, validitas identitas bot diverifikasi (*spoofing prevention*) dan latensi respons server dicatat. Rasio `HTTP 200` vs `HTTP 304` (Not Modified) mengindikasikan efisiensi penyerapan sumber daya *caching*.
2. **Resource Allocation (Crawl Budget Exhaustion)**: Crawl budget bukan angka statis, melainkan fungsi dinamis dari *Host Load Capacity* (kemampuan server melayani request tanpa degradasi latensi) dan *Crawl Demand* (popularitas dan frekuensi pembaruan konten). Peningkatan latensi TTFB (Time to First Byte) secara linear menurunkan *crawl limit* Googlebot.
3. **Algorithmic Diagnostics**: Penurunan performa organik sering kali disalahartikan sebagai penalti algoritmik (misal: Google Helpful Content Update atau Core Update), padahal akar masalahnya bisa berupa *silent infrastructure failure* (misal: bot dialihkan ke *infinite redirect loops*, lonjakan status `503 Service Unavailable`, atau kegagalan *edge SSR hydration*). Telemetri log real-time bertindak sebagai *ground truth* untuk memisahkan kedua fenomena ini.

---

### 3. Why It Matters

Dalam arsitektur web berskala jutaan halaman (misalnya platform e-commerce, agregator real-estate, atau media digital), kegagalan mendeteksi anomali bot secara dini menimbulkan kerugian bisnis langsung:

*   **Penyusutan Crawl Budget Akibat Bot Palsu**: Scraping bot yang menyamar sebagai `Googlebot` melalui manipulasi *User-Agent header* menyedot resource komputasi origin server dan memicu mekanisme *rate limiting* yang salah sasaran, sehingga bot resmi Google justru terhambat.
*   **Silent Technical Drops**: Misal, sebuah deploy microservice memicu *race condition* yang memunculkan status `500 Internal Server Error` khusus untuk request tanpa cookie otentikasi (karakteristik utama Googlebot). Google Search Console baru akan merefleksikan drop indeks 3 hingga 5 hari kemudian—menyebabkan penurunan visibilitas organik yang memakan waktu berminggu-minggu untuk dipulihkan.
*   **Ketidakmampuan Mengisolasi Dampak Algoritma**: Ketika terjadi Google Core Update berbarengan dengan rilis fitur web baru, enterprise tanpa real-time log analytics tidak memiliki data telemetri untuk membuktikan apakah penurunan ranking dipicu oleh evaluasi kualitas konten (*algorithmic assessment*) atau kegagalan rendering dan latensi server (*technical regression*).

---

### 4. Arsitektur & Diagram Komponen

Arsitektur ingestion pipeline log enterprise memproses ratusan ribu baris log per detik, memvalidasi bot, menormalisasi data, menyimpannya ke dalam columnar database, dan mengeksekusi analisis statistik secara terus-menerus:

```
+------------------------------------------------------------------------------------------------------------------------+
|                                                      EDGE LAYER                                                        |
|  [ Cloudflare Logpush / Fastly Real-time Syslog / AWS CloudFront Kinesis ]                                             |
+------------------------------------------------------------------------------------------------------------------------+
                                                       │  JSON Lines over TLS / gRPC (Zstandard compressed)
                                                       ▼
+------------------------------------------------------------------------------------------------------------------------+
|                                                  INGESTION BROKER                                                      |
|  [ Apache Kafka / Apache Pulsar Cluster ]                                                                              |
|  Topic: `edge-raw-access-logs` (Partitioned by Host/Domain)                                                           |
+------------------------------------------------------------------------------------------------------------------------+
                                                       │
                                                       ▼
+------------------------------------------------------------------------------------------------------------------------+
|                                            DISTRIBUTED STREAM WORKERS                                                  |
|  (Python / Go Consumer Group)                                                                                          |
|                                                                                                                        |
|   +-----------------------+     +-------------------------------+     +--------------------------------------------+   |
|   | 1. Log Normalization  | --> | 2. Bot Identity Verification  | --> | 3. Telemetry Feature Extraction            |   |
|   |    & URI Sanitization |     |    - Local Subnet CIDR Cache  |     |    - TTFB / Response Time                  |   |
|   +-----------------------+     |    - Redis Shared FQDN Cache  |     |    - HTTP Status Class (2xx, 3xx, 4xx, 5xx)|   |
|                                 |    - Async Double-rDNS Lookup |     |    - Depth & Page Type Classification      |   |
|                                 +-------------------------------+     +--------------------------------------------+   |
+------------------------------------------------------------------------------------------------------------------------+
                                                       │
                                                       ▼
+------------------------------------------------------------------------------------------------------------------------+
|                                                  PERSISTENCE LAYER                                                     |
|  [ ClickHouse Columnar Database Cluster ]                                                                              |
|  Tables:                                                                                                               |
|    - `edge_bot_logs_raw` (ReplacingMergeTree, Partitioned by Month, Primary Key: (bot_type, host, toStartOfHour(time))|
|    - `edge_bot_telemetry_1m` (AggregatingMergeTree for 1-minute Rollups)                                              |
+------------------------------------------------------------------------------------------------------------------------+
                                                       │
                                                       ▼
+------------------------------------------------------------------------------------------------------------------------+
|                                              DIAGNOSTIC & ANOMALY ENGINE                                               |
|  [ Async Background Daemon ]                                                                                           |
|  - CUSUM (Cumulative Sum Control Chart) for 5xx/429 Anomaly Spikes                                                     |
|  - Exponential Moving Average (EMA) Crawl Frequency Divergence                                                         |
|  - Alert Dispatcher (PagerDuty / Webhooks to Slack Ops Channel)                                                        |
+------------------------------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Verifikasi Bot Mesin Telusur Skala Enterprise

Memvalidasi identitas perayap (*crawler*) tidak boleh bergantung pada string `User-Agent` HTTP header semata, karena dapat dimanipulasi dengan mudah. Verifikasi dilakukan melalui protokol deterministik:

1. **Ekstraksi Header**: Dapatkan IP Klien (`Client-IP` atau `CF-Connecting-IP`) dan `User-Agent`.
2. **Filter Pola User-Agent**: Cek apakah string cocok dengan pola bot resmi (Googlebot, Bingbot, Yandex, Applebot). Jika tidak cocok, bypass langkah rDNS.
3. **CIDR Range Evaluation**: Evaluasi apakah IP berada dalam daftar subnet publik yang dirilis secara resmi oleh mesin pencari (misal: JSON IP ranges Google).
4. **Double Reverse DNS (rDNS Lookup)**:
   * Lakukan PTR record query untuk alamat IP asal.
   * Pastikan nama domain terverifikasi berakhir pada *top-level domain* resmi (misal: `.googlebot.com`, `.google.com`, `.search.msn.com`).
   * Lakukan resolusi *Forward DNS* (A/AAAA query) terhadap FQDN hasil resolusi PTR tersebut.
   * Cocokkan apakah IP hasil A/AAAA query identik dengan IP Klien asli.
5. **Caching Multi-Level**: Biaya komputasi rDNS per request sangat tinggi (latensi round-trip DNS 20–150 ms). Wajib diterapkan:
   * *L1 In-Memory LRU Cache* di level worker process (TTL: 24 jam).
   * *L2 Shared Redis Cache* di level kluster ingestion (TTL: 7 hari).

```
IP Request ───► [L1/L2 Cache Hit?] ───Yes───► Validated / Imposter
                     │
                     No
                     ▼
             [PTR Query on IP]
                     │ (Returns: crawl-66-249-66-1.googlebot.com)
                     ▼
      [Ends with .googlebot.com?] ───No────► Imposter (Spoofed)
                     │
                    Yes
                     ▼
         [Forward A/AAAA Query]
                     │ (Returns: 66.249.66.1)
                     ▼
          [Matches Origin IP?] ────Yes───► Validated Bot (Cache Result)
                     │
                     No
                     ▼
            Imposter (Spoofed)
```

#### B. Isolasi Deret Waktu untuk Anomali Crawling

Untuk memprediksi potensi *de-indexing* dan degradasi performa sebelum metrik visibilitas SERP terpengaruh, kita menerapkan algoritma **CUSUM (Cumulative Sum Control Chart)** terhadap tingkat error (rasio HTTP 5xx dan 429) serta frekuensi *crawling*.

Persamaan statistik CUSUM dua sisi (*two-sided CUSUM*) untuk mendeteksi pergeseran rata-rata:

$$S_H[t] = \max(0, S_H[t-1] + (X_t - (\mu_0 + K)))$$

$$S_L[t] = \max(0, S_L[t-1] + ((\mu_0 - K) - X_t))$$

Dimana:
- $X_t$ adalah rasio kegagalan (atau metrik latensi) pada interval waktu $t$.
- $\mu_0$ adalah nilai rata-rata referensi (*baseline mean*) yang dihitung saat sistem berjalan dalam kondisi stabil.
- $K$ adalah *allowance* atau *slack value*, umumnya ditentukan sebesar $\frac{\delta}{2} \cdot \sigma$ (dengan $\delta$ merupakan besar pergeseran minimum yang ingin dideteksi dalam deviasi standar $\sigma$).
- Jika akumulator $S_H[t] > H$ atau $S_L[t] > H$ (dengan $H$ sebagai batas ambang/*decision threshold*, umumnya $4\sigma$ atau $5\sigma$), maka anomali terdeteksi secara otomatis.

Ketika anomali $S_H[t]$ terpicu bersamaan dengan anomali latensi TTFB, sistem menandai insiden sebagai **Technical Bottleneck**. Sebaliknya, bila pola *crawling* anjlok secara asimetris pada direktori tertentu tanpa adanya lonjakan error server (latensi tetap rendah, status `200`), insiden ditandai sebagai **Algorithmic Reprioritization (Potential Quality Drop / Penalty)**.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi end-to-end ingestion pipeline worker yang mengonsumsi raw streaming logs, memverifikasi keaslian bot melalui asinkron rDNS caching, memasukkan metrik ke ClickHouse, dan mengevaluasi anomali deret waktu dengan CUSUM.

```python
#!/usr/bin/env python3
"""
Enterprise Edge Log Ingestion, Bot Verification & Telemetry Diagnostic Engine.
Architected for high-throughput SEO infrastructure monitoring.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import socket
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

import aiodns
import numpy as np

# Configure structured enterprise logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s", "level":"%(levelname)s", "module":"%(name)s", "message":"%(message)s"}',
)
logger = logging.getLogger("SEOIngestionEngine")


@dataclass(frozen=True)
class RawEdgeLog:
    timestamp: float
    client_ip: str
    user_agent: str
    request_uri: str
    status_code: int
    ttfb_ms: float
    host: str
    edge_colo: str


@dataclass(frozen=True)
class ProcessedLogEvent:
    timestamp: float
    client_ip: str
    bot_identity: str
    is_verified_bot: bool
    request_path: str
    status_code: int
    ttfb_ms: float
    host: str
    category: str


class BotVerificationEngine:
    """
    Asynchronous Bot Verification Engine using Multi-Tier Caching
    and Double Reverse DNS resolution.
    """

    ALLOWED_BOT_DOMAINS: Dict[str, Tuple[str, ...]] = {
        "google": (".googlebot.com", ".google.com"),
        "bing": (".search.msn.com",),
        "yandex": (".yandex.ru", ".yandex.net", ".yandex.com"),
    }

    BOT_UA_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
        ("google", re.compile(r"Googlebot|Mediapartners-Google|AdsBot-Google", re.IGNORECASE)),
        ("bing", re.compile(r"bingbot|BingPreview", re.IGNORECASE)),
        ("yandex", re.compile(r"YandexBot|YandexImages", re.IGNORECASE)),
    ]

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.resolver = aiodns.DNSResolver(loop=loop)
        # L1 In-Memory LRU Cache: ip -> (is_verified, bot_identity)
        self._cache: Dict[str, Tuple[bool, str]] = {}
        self._max_cache_size = 50000

    def _match_user_agent(self, user_agent: str) -> Optional[str]:
        for bot_id, pattern in self.BOT_UA_PATTERNS:
            if pattern.search(user_agent):
                return bot_id
        return None

    async def verify_bot(self, ip_str: str, user_agent: str) -> Tuple[bool, str]:
        """
        Conducts Double-rDNS validation with defensive error handling.
        """
        bot_family = self._match_user_agent(user_agent)
        if not bot_family:
            return False, "generic_client"

        # Check Cache
        if ip_str in self._cache:
            return self._cache[ip_str]

        # Validate IP format
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if ip_obj.is_private or ip_obj.is_loopback:
                return False, f"fake_{bot_family}_internal_ip"
        except ValueError:
            return False, "invalid_ip"

        # Begin Double-rDNS verification
        try:
            # 1. Reverse Lookup (PTR)
            ptr_result = await self.resolver.gethostbyaddr(ip_str)
            hostname = ptr_result.name.lower()

            # 2. Domain Match Check
            valid_domains = self.ALLOWED_BOT_DOMAINS.get(bot_family, ())
            if not any(hostname.endswith(suffix) for suffix in valid_domains):
                self._update_cache(ip_str, (False, f"spoofed_{bot_family}"))
                return False, f"spoofed_{bot_family}"

            # 3. Forward Lookup (A/AAAA)
            family_type = socket.AF_INET6 if ip_obj.version == 6 else socket.AF_INET
            forward_result = await self.resolver.gethostbyname(hostname, family_type)

            # 4. Check if resolved addresses match the originating IP
            if ip_str in forward_result.addresses:
                self._update_cache(ip_str, (True, bot_family))
                return True, bot_family
            else:
                self._update_cache(ip_str, (False, f"spoofed_{bot_family}"))
                return False, f"spoofed_{bot_family}"

        except (aiodns.error.DNSError, Exception) as dns_err:
            logger.debug(f"DNS Resolution failed for {ip_str}: {str(dns_err)}")
            # Do not permanently cache transient DNS failures
            return False, f"unverified_{bot_family}_dns_failure"

    def _update_cache(self, ip_str: str, result: Tuple[bool, str]) -> None:
        if len(self._cache) >= self._max_cache_size:
            # Evict arbitrary item to control memory footprint
            self._cache.pop(next(iter(self._cache)))
        self._cache[ip_str] = result


class CUSUMAnomalyDetector:
    """
    Cumulative Sum (CUSUM) Control Chart for tracking anomalies in
    error rates (5xx, 429) and crawl velocity shifts.
    """

    def __init__(self, mean_target: float, sigma: float, threshold_sigmas: float = 4.0) -> None:
        self.mu_0 = mean_target
        self.sigma = max(sigma, 1e-6)
        self.k = 0.5 * self.sigma  # Slack value
        self.h = threshold_sigmas * self.sigma  # Decision threshold
        self.s_high: float = 0.0
        self.s_low: float = 0.0

    def process_observation(self, x_t: float) -> Tuple[bool, str, float]:
        """
        Processes a single point in time, returning (is_anomaly, direction, current_s).
        """
        self.s_high = max(0.0, self.s_high + (x_t - (self.mu_0 + self.k)))
        self.s_low = max(0.0, self.s_low + ((self.mu_0 - self.k) - x_t))

        if self.s_high > self.h:
            reset_s = self.s_high
            self.s_high = 0.0  # Reset post-trigger
            return True, "HIGH_SURGE", reset_s
        elif self.s_low > self.h:
            reset_s = self.s_low
            self.s_low = 0.0  # Reset post-trigger
            return True, "LOW_DROP", reset_s

        return False, "STABLE", 0.0


class ClickHouseSinkMock:
    """
    Production ClickHouse buffer pool mock executing batched inserts.
    """

    def __init__(self) -> None:
        self.buffer: List[ProcessedLogEvent] = []
        self.batch_size = 500

    async def write(self, event: ProcessedLogEvent) -> None:
        self.buffer.append(event)
        if len(self.buffer) >= self.batch_size:
            await self.flush()

    async def flush(self) -> None:
        if not self.buffer:
            return
        records_to_flush = len(self.buffer)
        # ClickHouse HTTP interface or Native driver insertion logic executes here
        self.buffer.clear()
        logger.info(f"Successfully pushed batch of {records_to_flush} events to ClickHouse.")


class TelemetryDiagnosticPipeline:
    """
    Central orchestration engine processing streaming edge logs and executing
    real-time diagnostic algorithms.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.verifier = BotVerificationEngine(loop=loop)
        self.sink = ClickHouseSinkMock()
        self.error_rate_detector = CUSUMAnomalyDetector(mean_target=0.01, sigma=0.005, threshold_sigmas=4.0)

    def _categorize_path(self, uri: str) -> str:
        if uri.startswith("/product/"):
            return "pdp"
        elif uri.startswith("/category/"):
            return "plp"
        elif uri == "/" or uri.startswith("/?"):
            return "homepage"
        return "misc"

    async def process_log_line(self, raw_payload: str) -> Optional[ProcessedLogEvent]:
        try:
            data = json.loads(raw_payload)
            log = RawEdgeLog(
                timestamp=float(data["timestamp"]),
                client_ip=str(data["client_ip"]),
                user_agent=str(data["user_agent"]),
                request_uri=str(data["request_uri"]),
                status_code=int(data["status_code"]),
                ttfb_ms=float(data["ttfb_ms"]),
                host=str(data["host"]),
                edge_colo=str(data.get("edge_colo", "UNKNOWN")),
            )
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Malformed log payload discarded: {str(e)}")
            return None

        # Verify Crawler Validity
        is_verified, bot_identity = await self.verifier.verify_bot(log.client_ip, log.user_agent)

        event = ProcessedLogEvent(
            timestamp=log.timestamp,
            client_ip=log.client_ip,
            bot_identity=bot_identity,
            is_verified_bot=is_verified,
            request_path=log.request_uri,
            status_code=log.status_code,
            ttfb_ms=log.ttfb_ms,
            host=log.host,
            category=self._categorize_path(log.request_uri),
        )

        await self.sink.write(event)
        return event

    def run_telemetry_diagnostics(self, historical_error_rates: np.ndarray) -> None:
        """
        Iterates over windows to demonstrate algorithmic anomaly detection.
        """
        logger.info("Initializing CUSUM Diagnostic Sweep over latest ingestion window...")
        for idx, val in enumerate(historical_error_rates):
            is_anomaly, direction, score = self.error_rate_detector.process_observation(float(val))
            if is_anomaly:
                logger.error(
                    f"CRITICAL ANOMALY: Index {idx} detected {direction} in error rate! "
                    f"Score: {score:.4f}, Metric: {val:.4f}"
                )


# =====================================================================
# Unit Validation and Event-Loop Runner
# =====================================================================
async def main() -> None:
    loop = asyncio.get_running_loop()
    pipeline = TelemetryDiagnosticPipeline(loop)

    # Simulated edge log payloads
    raw_logs = [
        # Legitimate Googlebot (resolves properly via DNS in mock or real internet)
        json.dumps(
            {
                "timestamp": 1710500000.0,
                "client_ip": "66.249.66.1",
                "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                "request_uri": "/product/gpu-nvidia-rtx-4090",
                "status_code": 200,
                "ttfb_ms": 42.5,
                "host": "ecommerce.enterprise.internal",
            }
        ),
        # Malicious Scraper Spoofing Googlebot
        json.dumps(
            {
                "timestamp": 1710500001.0,
                "client_ip": "198.51.100.23",
                "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                "request_uri": "/category/electronics",
                "status_code": 429,
                "ttfb_ms": 12.1,
                "host": "ecommerce.enterprise.internal",
            }
        ),
    ]

    for raw in raw_logs:
        result = await pipeline.process_log_line(raw)
        if result:
            logger.info(
                f"Ingested Request: IP={result.client_ip} | Bot={result.bot_identity} | "
                f"Verified={result.is_verified_bot} | Status={result.status_code}"
            )

    await pipeline.sink.flush()

    # Synthetic Series: Constant error rate (0.01) jumping suddenly to 0.05
    synthetic_error_rates = np.concatenate([np.random.normal(0.01, 0.002, 30), np.random.normal(0.05, 0.004, 10)])
    pipeline.run_telemetry_diagnostics(synthetic_error_rates)


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

| Edge Case / Failure Mode | Mekanisme Kegagalan | Mitigasi Arsitektur |
| :--- | :--- | :--- |
| **DNS Exhaustion / Rate Throttling** | Ribuan rDNS lookup serentak menyebabkan DNS resolver upstream melakukan rate limiting atau mengalami *timeout*. | Gunakan distributed local DNS cache (Unbound/CoreDNS daemon di level pod/node) dengan shared Redis cluster untuk TTL caching multi-hari. |
| **Google Cloud Bot Impersonation** | Penyerang menyewa VM di Google Cloud Platform (GCP) yang memiliki PTR record berakhiran `.bc.googleusercontent.com` untuk mengelabui regex longgar. | Validasi ketat (*strict matching*) domain FQDN. Hanya izinkan akhiran domain level dua/tiga resmi: `.googlebot.com`, `.google.com`. |
| **High-Cardinality Request Paths** | Jutaan URL dinamis dengan query parameter acak membebani memori dan mengaburkan agregasi ClickHouse. | Terapkan normalisasi URL deterministik sebelum persistensi: stripping parameter pelacak (`utm_*`, `gclid`), masking ID numerik/UUID menjadi regex placeholder (misal: `/product/[uuid]`). |
| **Backpressure Spillover saat Spike Log** | Peningkatan *crawl rate* Googlebot hingga 10x lipat saat migrasi domain membuat worker out-of-memory (OOM). | Gunakan buffer streaming (Kafka/Pulsar) dengan *backpressure control*. Batasi *concurrency semaphore* pada distributed workers. |
| **Transient Edge-to-Origin Drops (HTTP 502/504)** | Edge server gagal menghubungi backend, mencatat status 502 di edge log sementara server origin tampak normal di metrics CPU/RAM. | Lakukan korelasi silang log edge CDN dengan *origin application APM tracing* (OpenTelemetry Span Context) menggunakan `traceparent` header. |

---

### 8. Trade-offs & Alternatif Solusi

#### 1. ClickHouse vs. Elasticsearch / OpenSearch

*   **Pilihan**: ClickHouse untuk SEO Telemetry Storage.
*   **Trade-off**: ClickHouse tidak memiliki kapabilitas *full-text search* tokenisasi tingkat lanjut seperti inverted index Elasticsearch. Namun, ClickHouse menggunakan kompresi berbasis kolom (ZSTD/LZ4) yang memangkas biaya penyimpanan log hingga 80%, serta memberikan kecepatan agregasi analitik puluhan miliar baris log per detik (kueri status codes, rilis crawl path, p99 TTFB) jauh melampaui kemampuan lucene-based engines.

#### 2. Real-Time In-Line Processing vs. Batch Micro-Chunking

*   **Real-Time Line-by-Line Ingestion**:
    *   *Kelebihan*: Deteksi anomali seketika ($< 5$ detik).
    *   *Kekurangan*: Beban I/O database tinggi, DNS lookup memicu latensi pipeline.
*   **Micro-Batching (Interval 10–60 detik via Object Storage / S3 Logpush)**:
    *   *Kelebihan*: Biaya komputasi lebih murah, parsing vectorized jauh lebih efisien.
    *   *Kekurangan*: Keterlambatan respons diagnostik 1–5 menit.
    *   *Rekomendasi Arsitektur*: Gunakan *hybrid approach*: Real-time edge filtering untuk status code kritis (`5xx`, `429`), dan *micro-batching* untuk analisis agregat pola struktural crawl log (status `200`, `304`).

---

### 9. Best Practices & Standard Industri

1. **Sinkronisasi IP Range Terjadwal**: Jalankan background cron job harian yang menyerap daftar CIDR resmi Googlebot (`https://developers.google.com/search/apis/ipranges/googlebot.json`) dan Bingbot (`https://www.bing.com/bingbot.json`). Gunakan IP trie lookup lokal di memori sebelum melakukan rDNS untuk menurunkan 90% network overhead.
2. **Standardisasi Status Tracking**: Pisahkan metrik status code berdasarkan spesifikasi RFC 9110:
   * **304 Not Modified**: Keberhasilan optimal crawl budget (Googlebot mengonsumsi metadata tanpa membebani throughput payload server).
   * **429 Too Many Requests**: Sinyal darurat teknis mutlak; Googlebot akan langsung memotong alokasi crawler speed.
   * **Soft 404 (200 OK dengan konten error)**: Pantau variasi ukuran respons HTTP (*Response Body Byte Length*); penurunan drastis ukuran HTML pada status 200 mengindikasikan halaman kosong atau render failure.
3. **Partitioning & Retention ClickHouse**: Partisi tabel log berdasarkan bulan (`toYYYYMM(timestamp)`) dan tetapkan Primary Key: `(bot_identity, host, toStartOfHour(timestamp), status_code)`. Terapkan TTL tabel ClickHouse: data raw dihapus setelah 30 hari, data roll-up 1-menit dipertahankan selama 365 hari.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan mendeteksi serangan *Crawl Spoofing Attack* yang menyebabkan lonjakan HTTP 429 pada origin cluster, serta memisahkan bot palsu tersebut dari Googlebot resmi.

#### Langkah 1: Siapkan File Mock Edge Log
Buat file `edge_stream.jsonl` berisi log campuran:
```bash
cat << 'EOF' > edge_stream.jsonl
{"timestamp": 1710500100.0, "client_ip": "66.249.66.1", "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "request_uri": "/catalog/item-01", "status_code": 200, "ttfb_ms": 32.1, "host": "prod.seo.internal"}
{"timestamp": 1710500101.0, "client_ip": "1.2.3.4", "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "request_uri": "/catalog/item-02", "status_code": 429, "ttfb_ms": 11.2, "host": "prod.seo.internal"}
{"timestamp": 1710500102.0, "client_ip": "66.249.66.2", "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "request_uri": "/catalog/item-03", "status_code": 200, "ttfb_ms": 28.4, "host": "prod.seo.internal"}
{"timestamp": 1710500103.0, "client_ip": "5.6.7.8", "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "request_uri": "/catalog/item-04", "status_code": 429, "ttfb_ms": 14.5, "host": "prod.seo.internal"}
EOF
```

#### Langkah 2: Buat Skrip Diagnostic Assertion
Buat skrip `lab_diagnostic.py` untuk mengisolasi request, memverifikasi anomali, dan menghasilkan laporan audit bot:

```python
import asyncio
import json
from typing import Counter


async def run_lab() -> None:
    # Simulasi verifikasi deterministic
    known_valid_ips = {"66.249.66.1", "66.249.66.2"}

    telemetry_counter: Counter[str] = Counter()
    spoofed_ips = []

    with open("edge_stream.jsonl", "r") as f:
        for line in f:
            record = json.loads(line)
            ip = record["client_ip"]
            status = record["status_code"]

            # Logika audit verifikasi bot
            if ip in known_valid_ips:
                bot_status = "VERIFIED_GOOGLEBOT"
            else:
                bot_status = "SPOOFED_BOT"
                spoofed_ips.append(ip)

            telemetry_counter[f"{bot_status}_HTTP_{status}"] += 1

    print("=== TELEMETRY INGESTION REPORT ===")
    for key, count in telemetry_counter.items():
        print(f"Metrics: {key:30} -> Count: {count}")

    print("\n=== SECURITY & SEO ACTIONABLE ===")
    print(f"Spoofed Bot IPs identified for Edge Firewall Block: {spoofed_ips}")

    # Assertions
    assert (
        telemetry_counter["VERIFIED_GOOGLEBOT_HTTP_200"] == 2
    ), "Audit failure: Valid bots should experience zero 429s."
    assert (
        telemetry_counter["SPOOFED_BOT_HTTP_429"] == 2
    ), "Audit failure: Spoofed traffic is improperly categorized."
    print("\n[SUCCESS] Lab diagnostics completed with 100% classification precision.")


if __name__ == "__main__":
    asyncio.run(run_lab())
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan skrip validasi berikut pada terminal Anda:
```bash
python3 lab_diagnostic.py
```

#### Verifikasi Output yang Diharapkan
Pastikan output mencerminkan pemisahan trafik bot secara akurat:
```
=== TELEMETRY INGESTION REPORT ===
Metrics: VERIFIED_GOOGLEBOT_HTTP_200    -> Count: 2
Metrics: SPOOFED_BOT_HTTP_429           -> Count: 2

=== SECURITY & SEO ACTIONABLE ===
Spoofed Bot IPs identified for Edge Firewall Block: ['1.2.3.4', '5.6.7.8']

[SUCCESS] Lab diagnostics completed with 100% classification precision.
```