# BAB 09: Enterprise Monitoring, Log Analysis & Algorithmic Impact Detection
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang dan mengimplementasikan** arsitektur *real-time log pipeline* terdistribusi berkemampuan menelan puluhan ribu *request per second* (RPS) dari edge CDN/load balancer untuk analitik bot mesin pencari.
- **Mengembangkan sistem verifikasi bot berbasis *Forward-Confirmed Reverse DNS* (FCrDNS)** dengan *in-memory caching* bertingkat untuk mengeliminasi *spoofed search engine crawlers* secara deterministik tanpa memperkenalkan latensi pada *hot-path* HTTP.
- **Membangun skema penyimpanan analitis *column-oriented* (ClickHouse)** yang dioptimasi untuk metrik SEO teknis: *crawl budget exhaustion*, *status code distribution*, *rendering latency*, dan rasio penelusuran *freshness* vs *stale content*.
- **Mengimplementasikan algoritma deteksi anomali deret waktu** (*Cumulative Sum* [CUSUM] dan *Seasonal Hybrid ESD* [S-H-ESD]) guna mengidentifikasi dampak pembaruan algoritma penelusuran (misal: *Google Core Update*, *Helpful Content System*) terhadap *crawl patterns* dan *organic visibility*.
- **Mengorkestrasi mekanisme mitigasi dinamis** (*dynamic rate-limiting*, *stale-while-revalidate edge routing*, dan *SSR fallback injection*) saat terdeteksi *crawl storm* atau penurunan performa indeksasi skala masif.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda harus memahami:
- **Arsitektur Sistem Terdistribusi**: Konsep *message streaming* (Apache Kafka/Redpanda), *storage engines* berbasis LSM-Tree vs. B-Tree, dan basis data *column-oriented* (ClickHouse).
- **Protokol Jaringan & Edge Computing**: HTTP/2 & HTTP/3 framing, TLS handshake, terminasi CDN (Cloudflare Workers, Fastly VCL, atau OpenResty/Nginx Lua).
- **DNS Internals**: Struktur PTR record, A/AAAA lookup, DNS resolver caching, dan mitigasi *cache poisoning*.
- **Dasar Statistika Terapan**: *Rolling mean*, *standard deviation*, analisis time-series, dan deteksi *outliers* pada distribusi data *non-Gaussian*.
- **Bahasa Pemrograman**: Go (minimal v1.21+) untuk *high-throughput stream processing* dan Python (v3.10+) untuk rekayasa analitik/deteksi anomali.

---

### 3. Concept & Internal Architecture

Analisis log tingkat *enterprise* untuk SEO tidak beroperasi pada agregasi log statis batch harian. Mesin perayap (Googlebot, Bingbot, Yandex) beroperasi dalam jendela diskrit waktu nyata: mereka merespons langsung terhadap metrik *Time to First Byte* (TTFB), ketersediaan *server resources*, dan dinamika struktur URL. Ketika terjadi kesalahan konfigurasi arsitektur atau *search engine core update*, penundaan deteksi selama 24 jam dapat mengakibatkan de-indeksasi jutaan halaman dengan kerugian finansial yang signifikan.

#### 3.1. Edge Log Ingestion & Forward-Confirmed Reverse DNS (FCrDNS)
Sebagian besar bot berbahaya (*bad bots*) memalsukan *User-Agent* Googlebot (`Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)`). Memvalidasi keaslian bot melalui IP range statis Google tidak lagi memadai karena rentang subnet Google Cloud Engine (GCE) sering kali tumpang tindih atau berubah secara dinamis.

Mekanisme FCrDNS wajib dilakukan:
1. **Ekstraksi IP**: Ambil *client IP* murni dari header edge (`CF-Connecting-IP`, `True-Client-IP`, atau `X-Forwarded-For`).
2. **Reverse DNS Lookup (rDNS)**: Lakukan kueri PTR record terhadap IP tersebut. Hasil yang valid harus berakhir dengan domain terverifikasi (misal: `.googlebot.com` atau `.google.com`).
3. **Forward DNS Lookup (fDNS)**: Ambil domain hasil rDNS, lalu lakukan kueri A/AAAA record kembali. Jika salah satu IP yang dihasilkan identik dengan *client IP* awal, maka bot dinyatakan **Valid (Authentic)**. Jika tidak cocok, bot ditandai sebagai **Spoofed/Imposter**.

Karena resolusi DNS melalui UDP/TCP memicu latensi tinggi (50ms–300ms), FCrDNS **tidak boleh** dieksekusi secara sinkron di *hot-path* penyajian konten pengguna, melainkan di *edge logging pipeline* asynchronous atau dipercepat menggunakan arsitektur *distributed two-tier cache* (L1 LRU Memory + L2 Redis).

#### 3.2. Storage Engine Topology: ClickHouse Vector Architecture
ClickHouse dipilih untuk menyimpan miliaran entri log perayapan karena kompresi kolom ekstrem (menggunakan LZ4 atau ZSTD) dan kemampuan komputasi vektor berbasis SIMD.

Arsitektur penyimpanan memecah data log ke dalam:
- **Temporal partitioning**: Berdasarkan bulan (`toYYYYMM(event_time)`).
- **Primary sorting keys**: Dirancang untuk mempercepat kueri *slicing* SEO teknis tersering: `(is_bot_verified, bot_name, status_code, path_crc32, event_time)`.
- **Pre-aggregated Projections / Materialized Views**: Menghitung secara kontinu rasio perayapan per sub-direktori, latensi TTFB rata-rata per kluster halaman, dan persentase kesalahan respons (4xx/5xx).

#### 3.3. Algorithmic Impact Anomaly Engine
Ketika Google meluncurkan *Core Update*, metrik penelusuran bot bergeser mendahului perubahan metrik posisi (SERP):
1. **Crawl Shift Detection**: Googlebot membatasi alokasi *crawl budget* pada *low-quality clusters* (ditandai dengan lonjakan interval perayapan ulang / *recrawl delay*).
2. **Rendering Bottleneck Shift**: Terjadi peningkatan tiba-tiba pada *Googlebot-Smartphone Rendering Fetch* versus *Standard Ingestion Fetch*.
3. **Algorithm Impact Engine Architecture**: Pipeline analitik mengekstraksi metrik harian per kategori template URL, kemudian menguji deviasi terhadap *baseline* menggunakan model **Seasonal Hybrid ESD (S-H-ESD)** untuk memisahkan anomali SEO murni dari pola fluktuasi mingguan normal (misal: penurunan perayapan di akhir pekan).

---

### 4. Why & What

| Dimensi | Google Search Console (GSC) | Traditional Web Analytics (GA4) | Real-time Enterprise Log Pipeline |
| :--- | :--- | :--- | :--- |
| **Data Latency** | 48 hingga 72 jam tunda (*batch latency*). | Waktu nyata, tetapi hanya melacak sesi berbasis JavaScript. | *Near real-time* (< 5 detik dari *edge hit* ke OLAP). |
| **Crawl Visibility** | Agregat terkompresi; sampling tinggi; URL level terbatas. | **Buta total** terhadap *search engine bots* (karena bot tidak mengeksekusi tag GA). | **100% visibilitas deterministik** pada setiap *hit* bot (200, 304, 404, 500, pengalihan 301/302). |
| **Bot Verification** | Tidak menyediakan verifikasi real-time per request IP. | Tidak relevan. | Verifikasi deterministik kriptografis/DNS (FCrDNS) di layer ingest. |
| **Actionability** | Retrospektif pasif (hanya pelaporan). | Mengukur konversi pengguna, bukan *crawl discovery*. | Proaktif: Dapat memicu pembersihan cache edge otomatis, *kill-switch* bot spoofing, dan mitigasi *crawl budget*. |

Mengapa log analysis krusial untuk SEO?
- **Crawl Budget Wastage**: Mengidentifikasi perayapan berlebih pada parameter URL yang tidak bernilai (*faceted navigation traps*).
- **Ghost 404 / Soft 404 Real-time Profiling**: Mengetahui kapan bot mengonsumsi ribuan halaman kosong sebelum halaman tersebut dikeluarkan dari indeks.
- **Orphan Pages Discovery**: Menemukan halaman internal yang secara reguler dirayap bot melalui *external backlinks* lama, padahal tautan internalnya sudah terputus.

---

### 5. How: Architectural Workflow Detail

Berikut adalah tahapan pemrosesan log end-to-end skala enterprise:

```
[ Edge Layer: Fastly / Cloudflare / OpenResty ]
       │
       ▼ (Syslog TCP / Kafka Streaming Sink)
[ Ingestion Gateway / Vector.dev / Fluentbit ]
       │
       ▼ (Decoupled Buffering Topic: "raw-edge-logs")
[ Message Broker: Apache Kafka / Redpanda Cluster ]
       │
       ├───► [ Bot Verification & Enrichment Engine (Go Worker Pool) ]
       │          │
       │          ├── [ L1: Local Cache (Ristretto) ]
       │          └── [ L2: Distributed Cache (Redis) ] ── (Miss) ──► [ Async DNS Resolver Pool ]
       │          │
       │          ▼ (Verified Topic: "enriched-bot-logs")
       ├───► [ ClickHouse Sink Connector ]
       │          │
       │          ▼
       │     [ ClickHouse Columnar Cluster ]
       │          │
       │          ├── Materialized View: Continuous Aggregates (Hourly/Daily)
       │          └── Primary Table: Raw Audit Trails (TTL 90 Days)
       │
       ▼
[ SEO Anomaly Detection Engine (Python Celery / Chronos) ]
       │
       ├── Run S-H-ESD / CUSUM Algorithm on Crawl Volume & Latency
       ├── Query SERP Rank Tracking Correlation
       │
       ▼ (Alert Triggered / Anomaly Confirmed)
[ Automated Remediation Control Plane ]
       ├── Purge Edge Cache on Stale Sections
       ├── Auto-apply Robots-Tag: "noindex, follow" on degraded sections
       └── Slack / PagerDuty Technical Incident Response
```

#### Langkah-langkah Pemrosesan Logika Operasional:
1. **Capture**: Edge layer mengekstrak struktur data mikro: IP, User-Agent, Path, Query Parameters, Response Status, Upstream Processing Time, TLS Version, dan Edge POP Location.
2. **Buffer**: Log dikirim melalui transport non-blocking ke Apache Kafka guna mencegah *backpressure* ke traffic produksi pengguna.
3. **Enrich & Verify**: Worker Go membaca *raw logs*. Jika User-Agent terdeteksi mengandung token bot target (`Googlebot`, `Bingbot`, dll.), sistem mengecek IP terhadap cache FCrDNS.
4. **Ingest**: Data terverifikasi ditulis ke ClickHouse secara batch (minimal 10.000 baris atau interval 1 detik) untuk memaksimalkan efisiensi kompresi disk blok LZ4.
5. **Analyze**: Anomaly Engine melakukan kueri analitik berbasis *time-bucket* secara terjadwal, menghitung z-score dari volume perayapan dan degradasi performa response time per URL pattern.

---

### 6. Analogy & Architecture Diagram

#### Analogi Konseptual
Bayangkan sebuah bandara internasional tersibuk di dunia:
- **Pengunjung Reguler (Pengguna)**: Penumpang yang membawa paspor fisik, tiket, dan koper.
- **Pemeriksa Paspor (FCrDNS Verification Worker)**: Menguji apakah orang yang mengenakan seragam pilot (*User-Agent Googlebot*) benar-benar terdaftar di maskapai penerbangan terkait, bukan sekadar kostum karnaval (*Bot Spoofing*). Pemeriksa tidak menghentikan arus penumpang di gerbang utama, melainkan memverifikasi kredensial mereka melalui radio khusus (*asynchronous queue*).
- **Log Perjalanan (ClickHouse)**: Buku catatan logistik khusus yang hanya mencatat jenis penerbangan, muatan, dan waktu tiba tanpa membuang ruang untuk detail yang redundan, disusun per maskapai untuk pencarian kilat.
- **Detektor Radar Wilayah Udara (Anomaly Detection Engine)**: Sistem yang memantau jika frekuensi pendaratan armada pesawat utama mendadak turun 40% dari hari-hari biasa tanpa adanya cuaca buruk—mengindikasikan perubahan izin rute penerbangan global (*Search Engine Core Update*).

#### Architectural Flow Diagram (ASCII)

```
+-----------------------------------------------------------------------------------------------+
|                                      CDN / EDGE INGRESS LAYER                                 |
|  - Cloudflare Worker / OpenResty Log Interceptor                                              |
|  - Non-blocking async dispatch of JSON-structured Access Log                                 |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v [TCP / Kafka Wire Protocol]
+-----------------------------------------------------------------------------------------------+
|                                APACHE KAFKA CLUSTER INGESTION                                 |
|  Topic: edge-access-logs-raw (Partitions: 32, Replica Factor: 3)                              |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                       GO STREAM WORKER POOL: VERIFIER & PARSER                                |
|                                                                                               |
|  +------------------+         +------------------------------------------------------------+  |
|  | Regex User-Agent |         | FCrDNS Verification Engine                                 |  |
|  | Classifier       | ------> | Step 1: Check In-Memory LRU (Cache Hit: 99.1%)             |  |
|  +------------------+         | Step 2: Check Redis Distributed Cache                      |  |
|                               | Step 3: Eviction/Miss -> Resolve PTR & Confirm A-Record    |  |
|                               +------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                        CLICKHOUSE CLUSTER (REAL-TIME ANALYTIC STORE)                          |
|                                                                                               |
|  Table: seo_bot_logs_raw                                                                      |
|  Engine = ReplicatedMergeTree('/clickhouse/tables/{shard}/seo_bot_logs_raw', '{replica}')     |
|  PARTITION BY toYYYYMM(timestamp)                                                             |
|  ORDER BY (is_verified, bot_family, status_code, path_cluster, timestamp)                     |
|                                                                                               |
|  Materialized View: mv_bot_crawl_metrics_hourly                                               |
|  Aggregates: count(), quantiles(0.50, 0.95, 0.99)(upstream_response_time)                     |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
|                          STATISTICAL ANOMALY & IMPACT ENGINE                                  |
|                                                                                               |
|  - Query sliding windows: (Today vs Baseline 14 Days)                                         |
|  - Algorithmic Models:                                                                        |
|    * CUSUM (Cumulative Sum Control Chart) for Latency Inflection                              |
|    * Generalized ESD (Extreme Studentized Deviate) on Crawl Volume Drops                      |
|                                                                                               |
|  Output: Trigger Autonomous Remediation via Webhook / Edge Cache Invalidation                 |
+-----------------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Fundamental FCrDNS Logic in Go
Berikut adalah implementasi dasar algoritma *Forward-Confirmed Reverse DNS* tanpa caching:

```go
package main

import (
	"context"
	"fmt"
	"net"
	"strings"
	"time"
)

// VerifyBotAuthenticity mengeksekusi validasi deterministik FCrDNS
func VerifyBotAuthenticity(ctx context.Context, ipStr string, expectedSuffix string) (bool, string, error) {
	ip := net.ParseIP(ipStr)
	if ip == nil {
		return false, "", fmt.Errorf("invalid IP address string: %s", ipStr)
	}

	// 1. Reverse DNS lookup (IP -> Hostnames)
	names, err := net.DefaultResolver.LookupAddr(ctx, ipStr)
	if err != nil || len(names) == 0 {
		return false, "", fmt.Errorf("reverse DNS (PTR) lookup failed: %w", err)
	}

	for _, name := range names {
		cleanName := strings.TrimSuffix(name, ".")
		// Validasi apakah suffix domain sesuai target (misal: .googlebot.com)
		if !strings.HasSuffix(strings.ToLower(cleanName), strings.ToLower(expectedSuffix)) {
			continue
		}

		// 2. Forward DNS lookup (Hostname -> IPs)
		targetIPs, err := net.DefaultResolver.LookupIP(ctx, "ip", cleanName)
		if err != nil {
			continue
		}

		// 3. Konfirmasi apakah original IP terdapat pada hasil Forward DNS
		for _, targetIP := range targetIPs {
			if targetIP.Equal(ip) {
				return true, cleanName, nil // Bot valid & terverifikasi
			}
		}
	}

	return false, "", nil
}

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	// IP simulasi: Googlebot IP riil vs Spoofed IP
	testIP := "66.249.66.1" // Googlebot IP yang valid
	isVerified, host, err := VerifyBotAuthenticity(ctx, testIP, ".googlebot.com")
	if err != nil {
		fmt.Printf("Validation error: %v\n", err)
	}
	fmt.Printf("Result -> IP: %s, Is Authentic: %t, Hostname: %s\n", testIP, isVerified, host)
}
```

#### 7.2. Practical Example: Industrial-Grade Pipeline Components

##### A. High-Performance Go Stream Processor (Worker dengan Tiered LRU Cache)
Komponen ini berjalan sebagai konsumen Kafka, memvalidasi bot dalam skala jutaan event harian tanpa membebani server DNS publik berkat *in-memory cache*.

```go
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/dgraph-io/ristretto"
)

type EdgeAccessLog struct {
	Timestamp            string  `json:"timestamp"`
	ClientIP             string  `json:"client_ip"`
	UserAgent            string  `json:"user_agent"`
	Method               string  `json:"method"`
	URI                  string  `json:"uri"`
	StatusCode           int     `json:"status_code"`
	UpstreamResponseTime float64 `json:"upstream_response_time"`
	EdgePOP              string  `json:"edge_pop"`
}

type EnrichedBotLog struct {
	EdgeAccessLog
	IsBot            bool   `json:"is_bot"`
	BotName          string `json:"bot_name"`
	IsVerifiedBot    bool   `json:"is_verified_bot"`
	ResolvedHostname string `json:"resolved_hostname"`
	PathCluster      string `json:"path_cluster"`
}

type VerificationResult struct {
	IsVerified bool
	Hostname   string
}

type BotEnricher struct {
	cache         *ristretto.Cache
	resolver      *net.Resolver
	clusterRegex  *regexp.Regexp
	botUserAgents map[string]string // Pattern -> Bot Family
}

func NewBotEnricher() (*BotEnricher, error) {
	cache, err := ristretto.NewCache(&ristretto.Config{
		NumCounters: 1e7,     // Jumlah key tracking counter (10 juta).
		MaxCost:     1 << 30, // Alokasi memori cache ~1GB.
		BufferItems: 64,      // Thread ring buffer size.
	})
	if err != nil {
		return nil, err
	}

	return &BotEnricher{
		cache: cache,
		resolver: &net.Resolver{
			PreferGo: true,
			Dial: func(ctx context.Context, network, address string) (net.Conn, error) {
				d := net.Dialer{Timeout: 500 * time.Millisecond}
				return d.DialContext(ctx, "udp", "1.1.1.1:53")
			},
		},
		clusterRegex: regexp.MustCompile(`^/([a-zA-Z0-9_-]+)`),
		botUserAgents: map[string]string{
			"Googlebot":   ".googlebot.com",
			"Bingbot":     ".search.msn.com",
			"YandexBot":   ".yandex.ru",
			"Baiduspider": ".crawl.baidu.com",
		},
	}, nil
}

func (e *BotEnricher) ProcessLog(ctx context.Context, raw []byte) (*EnrichedBotLog, error) {
	var rawLog EdgeAccessLog
	if err := json.Unmarshal(raw, &rawLog); err != nil {
		return nil, err
	}

	enriched := &EnrichedBotLog{
		EdgeAccessLog: rawLog,
		IsBot:         false,
		IsVerifiedBot: false,
	}

	// Ekstrak path cluster untuk agregasi di ClickHouse
	matches := e.clusterRegex.FindStringSubmatch(rawLog.URI)
	if len(matches) > 1 {
		enriched.PathCluster = "/" + matches[1]
	} else {
		enriched.PathCluster = "/root"
	}

	// Identifikasi Kandidat Bot berdasarkan User Agent
	var targetSuffix string
	for botToken, suffix := range e.botUserAgents {
		if strings.Contains(rawLog.UserAgent, botToken) {
			enriched.IsBot = true
			enriched.BotName = botToken
			targetSuffix = suffix
			break
		}
	}

	if !enriched.IsBot {
		return enriched, nil
	}

	// Verifikasi FCrDNS dengan Cache
	res, err := e.verifyCachedFCrDNS(ctx, rawLog.ClientIP, targetSuffix)
	if err == nil {
		enriched.IsVerifiedBot = res.IsVerified
		enriched.ResolvedHostname = res.Hostname
	}

	return enriched, nil
}

func (e *BotEnricher) verifyCachedFCrDNS(ctx context.Context, ipStr string, expectedSuffix string) (VerificationResult, error) {
	cacheKey := ipStr + ":" + expectedSuffix
	if val, found := e.cache.Get(cacheKey); found {
		return val.(VerificationResult), nil
	}

	result := VerificationResult{IsVerified: false, Hostname: ""}

	names, err := e.resolver.LookupAddr(ctx, ipStr)
	if err != nil || len(names) == 0 {
		e.cache.SetWithTTL(cacheKey, result, 1, 6*time.Hour)
		return result, nil
	}

	ip := net.ParseIP(ipStr)
	for _, name := range names {
		cleanName := strings.TrimSuffix(name, ".")
		if strings.HasSuffix(strings.ToLower(cleanName), strings.ToLower(expectedSuffix)) {
			targetIPs, err := e.resolver.LookupIP(ctx, "ip", cleanName)
			if err != nil {
				continue
			}
			for _, targetIP := range targetIPs {
				if targetIP.Equal(ip) {
					result.IsVerified = true
					result.Hostname = cleanName
					e.cache.SetWithTTL(cacheKey, result, 1, 24*time.Hour)
					return result, nil
				}
			}
		}
	}

	e.cache.SetWithTTL(cacheKey, result, 1, 12*time.Hour)
	return result, nil
}
```

##### B. Enterprise ClickHouse DDL & Materialized View
Skema berikut menggunakan enkripsi kompresi ganda (`DoubleDelta`, `T64`, `ZSTD`) dan materialisasi agregat untuk menangani beban analitik tinggi:

```sql
-- Database Inisialisasi
CREATE DATABASE IF NOT EXISTS seo_analytics;

-- Tabel Utama: Penyimpanan Akses Log Bot Mentah
CREATE TABLE IF NOT EXISTS seo_analytics.bot_access_logs
(
    event_timestamp       DateTime64(3, 'UTC') CODEC(DoubleDelta, ZSTD(1)),
    client_ip             IPv6                 CODEC(ZSTD(3)),
    is_verified           UInt8                CODEC(T64, ZSTD(1)),
    bot_family            LowCardinality(String),
    http_method           LowCardinality(String),
    uri                   String               CODEC(ZSTD(6)),
    path_cluster          LowCardinality(String),
    status_code           UInt16               CODEC(T64, ZSTD(1)),
    upstream_latency_ms   Float32              CODEC(Gorilla, ZSTD(1)),
    edge_pop              LowCardinality(String),
    user_agent            String               CODEC(ZSTD(4)),
    resolved_hostname     String               CODEC(ZSTD(3))
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/bot_access_logs', '{replica}')
PARTITION BY toYYYYMM(event_timestamp)
PRIMARY KEY (is_verified, bot_family, path_cluster)
ORDER BY (is_verified, bot_family, path_cluster, status_code, event_timestamp)
TTL toDateTime(event_timestamp) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- Materialized View: Continuous Rollup Agregasi Per Jam
CREATE TABLE IF NOT EXISTS seo_analytics.bot_hourly_metrics
(
    metric_hour           DateTime             CODEC(DoubleDelta, ZSTD(1)),
    bot_family            LowCardinality(String),
    path_cluster          LowCardinality(String),
    is_verified           UInt8,
    total_crawls          UInt64               CODEC(T64, ZSTD(1)),
    error_4xx_count       UInt64               CODEC(T64, ZSTD(1)),
    error_5xx_count       UInt64               CODEC(T64, ZSTD(1)),
    median_latency_ms     Float64,
    p95_latency_ms        Float64
)
ENGINE = SummingMergeTree()
PRIMARY KEY (is_verified, bot_family, path_cluster)
ORDER BY (is_verified, bot_family, path_cluster, metric_hour);

CREATE MATERIALIZED VIEW IF NOT EXISTS seo_analytics.mv_bot_hourly_metrics
TO seo_analytics.bot_hourly_metrics AS
SELECT
    toStartOfHour(event_timestamp) AS metric_hour,
    bot_family,
    path_cluster,
    is_verified,
    count() AS total_crawls,
    countIf(status_code >= 400 AND status_code < 500) AS error_4xx_count,
    countIf(status_code >= 500 AND status_code < 600) AS error_5xx_count,
    quantile(0.50)(upstream_latency_ms) AS median_latency_ms,
    quantile(0.95)(upstream_latency_ms) AS p95_latency_ms
FROM seo_analytics.bot_access_logs
GROUP BY
    metric_hour,
    bot_family,
    path_cluster,
    is_verified;
```

##### C. Production Anomaly Detection Engine (Python)
Script ini mengeksekusi algoritma Seasonal Hybrid Extreme Studentized Deviate (S-H-ESD) menggunakan *rolling seasonal decomposition* guna mendeteksi penurunan intensitas crawl setelah terjadinya *Google Core Update*.

```python
import numpy as np
import pandas as pd
from scipy import stats
import clickhouse_connect
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class CrawlAnomalyDetector:
    def __init__(self, clickhouse_client):
        self.client = clickhouse_client

    def fetch_historical_series(self, path_cluster: str, bot_family: str = 'Googlebot', days: int = 30) -> pd.DataFrame:
        query = f"""
        SELECT
            toStartOfHour(event_timestamp) as timestamp,
            count() as crawl_count,
            quantile(0.95)(upstream_latency_ms) as p95_latency
        FROM seo_analytics.bot_access_logs
        WHERE
            is_verified = 1
            AND bot_family = '{bot_family}'
            AND path_cluster = '{path_cluster}'
            AND event_timestamp >= now() - INTERVAL {days} DAY
        GROUP BY timestamp
        ORDER BY timestamp ASC
        """
        result = self.client.query_df(query)
        result['timestamp'] = pd.to_datetime(result['timestamp'])
        result.set_index('timestamp', inplace=True)
        # Reindex untuk memastikan tidak ada interval data yang hilang (hourly frequency)
        full_idx = pd.date_range(start=result.index.min(), end=result.index.max(), freq='H')
        return result.reindex(full_idx, fill_value=0)

    @staticmethod
    def detect_anomalies_s_h_esd(series: pd.Series, max_anomalies: float = 0.05, alpha: float = 0.05) -> pd.DataFrame:
        """
        Seasonal Hybrid Extreme Studentized Deviate (S-H-ESD)
        Memisahkan seasonality dengan STL/Median Loess lalu melakukan modified Z-score test.
        """
        # 1. Hitung seasonal component sederhana (24-hour periodicity median)
        df = pd.DataFrame({'value': series})
        df['hour'] = df.index.hour
        seasonal_profile = df.groupby('hour')['value'].median()
        
        # 2. Residu (Deseasonalized + Demedianed)
        df['seasonal'] = df['hour'].map(seasonal_profile)
        df['residual'] = df['value'] - df['seasonal']
        
        # Median Absolute Deviation (MAD) untuk estimasi dispersi yang tangguh (robust)
        median = df['residual'].median()
        mad = (df['residual'] - median).abs().median()
        if mad == 0:
            mad = 1.0e-6

        # Modified Z-Score
        df['z_score'] = 0.6745 * (df['residual'] - median) / mad
        
        # Ambang batas ESD dua arah
        n = len(df)
        k = int(n * max_anomalies)
        anomalies = df[df['z_score'].abs() > stats.norm.ppf(1 - alpha / (2 * n))].copy()
        
        return anomalies

    def run_pipeline(self, target_clusters: list[str]):
        for cluster in target_clusters:
            logging.info(f"Analyzing crawl variance for cluster: {cluster}")
            data = self.fetch_historical_series(path_cluster=cluster)
            if len(data) < 72:
                logging.warning(f"Data point insufficient for cluster: {cluster}, skipping.")
                continue

            anomalies = self.detect_anomalies_s_h_esd(data['crawl_count'])
            
            # Cek anomali dalam 6 jam terakhir
            recent_anomalies = anomalies[anomalies.index >= (pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(hours=6))]
            
            if not recent_anomalies.empty:
                for ts, row in recent_anomalies.iterrows():
                    direction = "DROP" if row['z_score'] < 0 else "SURGE"
                    logging.critical(
                        f"[ANOMALY DETECTED] Cluster: {cluster} | Direction: {direction} | "
                        f"Timestamp: {ts} | Value: {row['value']} | Robust Z-Score: {row['z_score']:.2f}"
                    )
                    # Di sini: Eksekusi Webhook alerting ke Slack / PagerDuty / Edge Invalidator

if __name__ == "__main__":
    ch_client = clickhouse_connect.get_client(host='localhost', port=8123, username='default', password='')
    detector = CrawlAnomalyDetector(ch_client)
    detector.run_pipeline(target_clusters=['/product', '/category', '/brand'])
```

---

### 8. Real World Case Study: E-Commerce Multinasional (50 Juta URL)

#### Masalah
Sebuah platform e-commerce dengan indeks lebih dari 50 juta produk mengalami penurunan perayapan Googlebot sebesar **68%** dalam tempo 10 hari setelah peluncuran fitur faceted filter dinamis. Penurunan ini memicu de-indeksasi bertahap pada *long-tail products* berpendapatan tinggi. Tim SEO menduga adanya pembaruan algoritma Google Core Update.

#### Investigasi Arsitektur
Melalui implementasi pipeline di atas, ditemukan temuan berikut:
1. **Faceted Trap**: Filter dinamis menghasilkan variasi kombinasi tak terbatas (misal: `/product?color=red&size=m&sort=asc&view=grid&page=...`), menciptakan miliaran URL semu berkonten serupa (*duplicate content*).
2. **Reverse DNS Analysis**: Log awal menunjukkan 40% trafik crawler berasal dari bot pemalsu identitas Googlebot (*bad bots* yang melakukan *scraping harga*), menguras alokasi koneksi pool origin load balancer.
3. **TTFB Inflation**: Akibat *scraping storm* tersebut, upstream latency (TTFB) origin membengkak dari 180ms ke 2.4 detik. Googlebot asli mendeteksi degradasi performa origin dan secara otomatis menurunkan *host crawl rate limiter*.

```
[Normal Baseline]     ---> Origin TTFB: 180ms  ---> Googlebot Daily Crawls: 12.000.000 URLs
[Faceted Trap Surge]  ---> Origin TTFB: 2400ms ---> Googlebot Self-Throttling (Drop 68% -> 3.840.000 URLs)
```

#### Solusi yang Diterapkan
1. **Edge-level FCrDNS Verification**:
   - Memasang layer autentikasi FCrDNS sinkron di Cloudflare Worker untuk *request* yang mengaku sebagai Googlebot.
   - Jika `is_verified == false`, *request* langsung dikenakan tantangan *Managed Challenge* (halaman CAPTCHA). Sebanyak 40% trafik liar berhasil diblokir di edge network.
2. **Dynamic Invalidation & Canonicalization**:
   - Pola query string faceted dinonaktifkan dari indeks melalui injeksi header edge otomatis: `X-Robots-Tag: noindex, follow` untuk URL dengan parameter lebih dari 2 kombinasi filter.
   - Peta `robots.txt` disesuaikan secara real-time via CDN rule untuk memblokir perayapan path filter kombinasi.
3. **Recovery Verification**:
   - Dalam 72 jam, TTFB origin kembali stabil di 165ms.
   - Metrik perayapan pada *Materialized View* ClickHouse menunjukkan Googlebot merestorasi kuota perayapannya hingga 14.500.000 URLs/hari, memicu pemulihan peringkat dan pengembalian trafik organik dalam siklus *refresh* algoritma berikutnya.

---

### 9. Trade-offs: Engineering Decisions

| Dimensi Arsitektur | Pilihan A | Pilihan B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Verifikasi FCrDNS** | **Synchronous at Edge** (Cloudflare Worker/OpenResty langsung memblokir). | **Asynchronous in Stream Worker** (Verifikasi pasif di pipeline Kafka/Go). | Edge Sync menghilangkan trafik bot palsu sebelum membebani origin, namun menambah latensi DNS lookup (20ms-150ms) jika terjadi *cache miss*. Asynchronous menjamin zero-latency untuk pengguna, namun origin sempat melayani bot palsu sebelum dievaluasi. |
| **Database Storage Format** | **Columnar OLAP (ClickHouse)** | **Elasticsearch / OpenSearch** | ClickHouse unggul dalam rasio kompresi data mentah (hingga 85-90% penghematan disk via ZSTD) dan kecepatan pemindaian triliunan baris aggregasi. Namun, ClickHouse memiliki kompleksitas tinggi pada mutasi data point individual (`UPDATE`/`DELETE`). Elasticsearch menawarkan kapabilitas kueri teks bebas yang lebih fleksibel, tetapi memakan RAM/disk hingga 4x lebih besar. |
| **Granularitas Data Log** | **Full Raw Logging (Simpan setiap baris)** | **Edge Metric Sampling (10% sampling rate)** | Full Raw Logging esensial untuk mendeteksi *individual URL crawl patterns* dan soft 404 traps secara deterministik, namun membutuhkan kapasitas storage masif. Sampling menghemat biaya infrastruktur, namun menyebabkan anomali pada sub-cluster URL bervolume rendah (*long-tail*) tidak terdeteksi. |
| **TTL Cache DNS Resolusi** | **Agresif (24 - 48 Jam)** | **Konservatif (15 - 60 Menit)** | TTL panjang memangkas *resolver latency* hingga mendekati nol (rasio cache hit > 99%), namun rentan terhadap *IP drift* jika Googlebot mengubah alokasi blok IP secara mendadak. TTL pendek mencegah *false positive authentication*, tetapi memicu lonjakan beban DNS outbound. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Mengabaikan Validasi Forward DNS (Hanya Mengandalkan PTR)
- **Gejala**: Penyerang membuat PTR record palsu di name server mereka sendiri (misal: `198.51.100.1` diarahkan ke `crawl-66-249-66-1.googlebot.com`).
- **Penyebab**: Kode verifikasi hanya memeriksa apakah nama host PTR diakhiri dengan `.googlebot.com`, tanpa melakukan pengecekan balik *A-Record* (Forward Lookup) ke nama domain tersebut.
- **Solusi**: Selalu jalankan validasi dua arah (FCrDNS). IP harus memiliki PTR yang mengarah ke domain resmi, dan domain resmi tersebut harus menyelesaikan kembali ke IP sumber.

#### 2. ClickHouse Partition Key Explosion
- **Gejala**: ClickHouse mengalami degradasi kinerja drastis, memicu error `Too many parts in all data in table`.
- **Penyebab**: Pengembang menggunakan partisi berbasis hari atau jam: `PARTITION BY toYYYYMMDD(event_timestamp)`. Pola ini menciptakan ribuan *data parts* kecil yang memicu kegagalan sistem kompresi *background merge*.
- **Solusi**: Gunakan partisi bulanan: `PARTITION BY toYYYYMM(event_timestamp)` dan andalkan `ORDER BY` untuk pengurutan data temporal di dalam partisi.

#### 3. Blocking Valid Search Bots via WAF Rate Limiting
- **Gejala**: Penurunan drastis (*drop*) volume perayapan Googlebot ke tingkat nol setelah dilakukan migrasi WAF.
- **Penyebab**: Rate-limiter WAF menganggap lonjakan koneksi paralel dari puluhan IP Googlebot sebagai serangan Distributed Denial of Service (DDoS) layer 7.
- **Solusi**: Masukkan modul FCrDNS ke dalam rule evaluasi WAF sebelum threshold rate limit dieksekusi, atau buat *bypass list* dinamis berbasis *verified crawler IP pool*.

---

### 11. Best Practices & Production Checklist

#### Production Checklist

##### Edge Layer & Ingestion:
- [ ] Non-blocking I/O pada edge logging: Syslog disalurkan melalui socket UDP atau memory-buffered TCP sink.
- [ ] Sanitasi Query String sensitif: Hapus token otentikasi (JWT, Session ID, PII) di edge sebelum log dikirim ke message broker.
- [ ] Sinkronisasi waktu sistem (NTP) dengan deviasi di bawah 5 milidetik di semua edge POP cluster.

##### Verification & Caching:
- [ ] Terapkan two-tier caching untuk verifikasi bot: L1 *in-memory* (Ristretto/BigCache di Go) dan L2 distributed key-value store (Redis).
- [ ] Atur TTL Cache PTR: 24 jam untuk record positif, 1 jam untuk record negatif (*NXDOMAIN*).
- [ ] Gunakan private recursive DNS resolver lokal (misal: Unbound dengan DNSSEC enabled) untuk meminimalkan latensi outbound.

##### ClickHouse Configuration:
- [ ] Kolom bertipe string dengan kardinalitas rendah (`method`, `edge_pop`, `bot_family`) wajib menggunakan tipe `LowCardinality(String)`.
- [ ] Kompresi ZSTD level 3-6 untuk URL path dan User-Agent.
- [ ] Aktifkan `optimize_aggregation_in_order = 1` pada kueri analitik dashboard.

##### Monitoring & Alerting:
- [ ] Pantau status *Kafka Consumer Group Lag*: Pastikan antrean log bot diproses dalam jendela latensi sub-detik.
- [ ] Setup trigger ambang batas CUSUM: Munculkan alert level Warning jika terjadi pergeseran *crawl distribution* lebih dari 20% selama 6 jam berturut-turut.

---

### 12. Hands-on Practice: Membangun Pipeline Real-time

Simpan seluruh file praktikum ini di direktori: `hands-on/m02/`

#### Struktur Direktori:
```
hands-on/m02/
├── docker-compose.yml
├── fluent-bit.conf
├── clickhouse-init.sql
└── test_pipeline.sh
```

#### Step 1: Buat `docker-compose.yml`
Menyediakan stack ClickHouse, Fluent-Bit (log forwarder), dan mock log generator.

```yaml
version: '3.8'

services:
  clickhouse:
    image: clickhouse/clickhouse-server:23.8-alpine
    container_name: ch_server
    ports:
      - "8123:8123"
      - "9000:9000"
    environment:
      - CLICKHOUSE_DB=seo_analytics
    volumes:
      - ./clickhouse-init.sql:/docker-entrypoint-initdb.d/init.sql
    ulimits:
      nofile:
        soft: 262144
        hard: 262144

  fluent-bit:
    image: fluent/fluent-bit:2.1
    container_name: fb_forwarder
    volumes:
      - ./fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf
    ports:
      - "24224:24224"
      - "24224:24224/udp"
    depends_on:
      - clickhouse
```

#### Step 2: Buat `clickhouse-init.sql`
Inisialisasi skema penampung log akses bot sederhana:

```sql
CREATE DATABASE IF NOT EXISTS seo_analytics;

CREATE TABLE IF NOT EXISTS seo_analytics.bot_access_logs
(
    event_timestamp       DateTime DEFAULT now(),
    client_ip             String,
    user_agent            String,
    uri                   String,
    status_code           UInt16,
    upstream_latency_ms   Float32
)
ENGINE = MergeTree()
ORDER BY (status_code, event_timestamp);
```

#### Step 3: Konfigurasi `fluent-bit.conf`
Mengonfigurasi parser HTTP dan sink langsung ke endpoint ClickHouse HTTP API:

```ini
[SERVICE]
    Flush        1
    Daemon       Off
    Log_Level    info

[INPUT]
    Name         http
    Listen       0.0.0.0
    Port         24224

[OUTPUT]
    Name         http
    Match        *
    Host         clickhouse
    Port         8123
    URI          /?query=INSERT+INTO+seo_analytics.bot_access_logs(client_ip,user_agent,uri,status_code,upstream_latency_ms)+FORMAT+JSONEachRow
    Format       json_stream
    json_date_key false
```

#### Step 4: Buat `test_pipeline.sh`
Skrip simulasi perayapan bot legal, penyerang spoofing, serta eksekusi kueri ClickHouse:

```bash
#!/usr/bin/env bash
set -e

echo "[1/3] Menjalankan Infrastruktur Pipeline via Docker..."
docker compose up -d

echo "Menunggu ClickHouse siap..."
sleep 5

echo "[2/3] Mengirimkan Simulasi Log Perayapan..."
# 1. Googlebot Hit
curl -s -X POST -H "Content-Type: application/json" -d '{
    "client_ip": "66.249.66.1",
    "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "uri": "/product/gpu-rtx-4090",
    "status_code": 200,
    "upstream_latency_ms": 124.5
}' http://localhost:24224/

# 2. Spoofed Googlebot Hit (IP tidak valid)
curl -s -X POST -H "Content-Type: application/json" -d '{
    "client_ip": "185.220.101.5",
    "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "uri": "/admin/config",
    "status_code": 403,
    "upstream_latency_ms": 12.1
}' http://localhost:24224/

# 3. Normal User Hit
curl -s -X POST -H "Content-Type: application/json" -d '{
    "client_ip": "114.122.45.10",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "uri": "/checkout",
    "status_code": 200,
    "upstream_latency_ms": 340.2
}' http://localhost:24224/

sleep 3

echo "[3/3] Melakukan Kueri Audit Log Langsung ke ClickHouse:"
curl -s "http://localhost:8123/?query=SELECT+client_ip,user_agent,uri,status_code,upstream_latency_ms+FROM+seo_analytics.bot_access_logs+FORMAT+Pretty"

echo "Praktikum Selesai!"
```

---

### 13. Exercises

#### Level: Easy
Modifikasi kueri Materialized View ClickHouse di atas untuk menyertakan persentase pengalihan 3xx (`countIf(status_code >= 300 AND status_code < 400)`).
*Tujuan*: Memahami bagaimana penelusuran rantai redirect (*redirect chains*) mengonsumsi anggaran perayapan bot.

#### Level: Medium
Tulis sebuah fungsi di Go yang menerima slice IP address dan mengelompokkannya secara konkuren (menggunakan goroutine dan worker pool) ke dalam subnet prefix `/24` untuk IPv4 atau `/48` untuk IPv6 sebelum melakukan resolve DNS, guna mendeteksi *distributed crawling farm*.

#### Level: Hard
Kembangkan script Python yang menghitung moving correlation coefficient (Pearson $r$) antara variasi harian Googlebot perayapan (dari ClickHouse) dan histori posisi SERP harian (dari dataset eksternal). Bila $r > 0.7$ dengan lag 3 hari, sistem harus otomatis mengeluarkan instruksi pembersihan cache (purge cache) untuk kluster path terkait.

---

### 14. Challenges

#### Skenario Kasus: Multi-Region CDN Crawl Budget Bleeding & Core Update Collapse
Sebuah marketplace real-estate enterprise beroperasi di 4 regional (US, EU, APAC, LATAM) dengan backend hybrid multi-cloud. Pasca peluncuran *Search Engine Quality Update*, metrik penelusuran menunjukkan fenomena aneh:
1. Crawl rate Googlebot di Region APAC drop sebesar 82%, sementara di Region US stabil.
2. Latensi TTFB rata-rata untuk dynamic product pages di Region APAC melonjak menjadi 1.8 detik hanya ketika dirayap oleh `Googlebot-Smartphone`, namun stabil di 220ms saat diakses browser desktop pengguna lokal.
3. Arsitektur menggunakan Fastly CDN di edge dan Kubernetes di origin.

#### Tugas Rekayasa Anda:
1. Rancang root-cause analysis architecture untuk mengisolasi anomali ini: Apakah ini penalti algoritma Google, kesalahan perutean geolokasi CDN, atau *SSR rendering failure* pada mobile user-agent?
2. Desain skema pipeline log ClickHouse yang dapat mengorelasikan secara real-time metrik `POP Location`, `Device-Type (Mobile vs Desktop)`, `Cache-Hit-Ratio`, dan `TCP Handshake Latency`.
3. Tulis blueprint arsitektur mitigasi otomatis di CDN edge untuk mengembalikan performa perayapan dalam waktu kurang dari 24 jam tanpa melakukan *restart* cluster origin.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa alasan utama verifikasi FCrDNS wajib melibatkan Forward DNS lookup setelah Reverse DNS lookup?
   - A. Forward DNS mempercepat proses handshake HTTP/3.
   - B. Siapa pun dapat mengonfigurasi PTR record sembarang pada IP publik yang mereka miliki untuk meniru domain Google.
   - C. Forward DNS dibutuhkan untuk mengonversi IPv6 menjadi format string IPv4.
   - D. Mesin pencari mengharuskan Forward DNS lookup sebagai prasyarat indexing JSON-LD.

2. Mengapa Google Search Console (GSC) tidak dapat menggantikan fungsi real-time access log monitoring?
   - A. GSC mengenakan biaya komputasi tambahan untuk setiap URL yang diperiksa.
   - B. GSC tidak mengindeks link yang memiliki atribut nofollow.
   - C. Data GSC mengalami penundaan (delay) 48–72 jam dan merupakan hasil sampling agregat.
   - D. GSC hanya mencatat respons dengan status code 200 OK.

3. Engine ClickHouse mana yang paling optimal untuk menyimpan metrik agregasi ringkasan perayapan bot secara kontinu?
   - A. Memory Engine
   - B. TinyLog
   - C. SummingMergeTree
   - D. Log Engine

4. Apa dampak negatif langsung terhadap performa ClickHouse jika skema log menggunakan partisi harian (`PARTITION BY toYYYYMMDD(event_timestamp)`) pada traffic berskala ribuan RPS?
   - A. Kompresi data ZSTD dinonaktifkan secara otomatis.
   - B. Terjadi ledakan jumlah partisi disk (too many parts) yang membebani background merge process.
   - C. Terjadi kebocoran memori pada thread TLS balancer.
   - D. Kueri status code selalu mengembalikan nilai NULL.

5. Header HTTP mana yang umumnya mengindikasikan IP klien asli ketika sistem berada di balik CDN Cloudflare?
   - A. `X-Cache-Status`
   - B. `CF-Connecting-IP`
   - C. `Forwarded-Proto`
   - D. `X-Real-Host`

---

#### Bagian 2: Intermediate (Pertanyaan Esai Singkat)
1. Jelaskan bagaimana *cache poisoning* pada resolver DNS internal dapat merusak integritas data pada *Bot Enrichment Worker*!
2. Mengapa agregasi latensi perayapan bot lebih tepat dihitung menggunakan persentil (p95 / p99) ketimbang nilai rata-rata (*mean*)?
3. Sebutkan dua metrik log yang membuktikan bahwa Googlebot sedang terjebak dalam *infinite crawler loop* (crawl trap)!
4. Dalam arsitektur stream-processing berbasis Kafka, mengapa parsing log mentah dan verifikasi DNS harus dipisahkan ke dalam *consumer group* yang berbeda dengan proses *batch writing* ke ClickHouse?
5. Bagaimana cara membedakan antara penurunan perayapan bot akibat *infrastructure failure* internal dan penurunan akibat *Google Quality Algorithm Demotion*?

---

#### Bagian 3: Production Case Scenarios

##### Kasus A
Pipeline Kafka Anda mengalami lonjakan *consumer lag* yang ekstrem (dari 100 event menjadi 2.500.000 event dalam 15 menit) setelah CDN mengalihkan seluruh log bot global ke pipeline logging baru. CPU worker Go mencapai 100%, dan latensi antrean terus meningkat. 

*Pertanyaan*: Langkah mitigasi arsitektur apa yang harus diambil secara instan untuk menstabilkan pipeline tanpa kehilangan data log, dan apa optimasi kode permanen yang harus diimplementasikan pada bot enrichment worker?

##### Kasus B
Sebuah audit menemukan bahwa 85% data yang disimpan pada tabel `bot_access_logs` di ClickHouse berstatus `is_verified = 0` (unverified/malicious bots), namun tabel ini tetap menghabiskan 80TB storage storage tier tercepat (NVMe SSD). 

*Pertanyaan*: Rancang strategi partisi, storage tiering (ClickHouse Multi-Volume Storage), dan lifecycle policy TTL untuk memangkas biaya infrastruktur ClickHouse tanpa kehilangan visibilitas historis terhadap bot resmi (Google/Bing)!

##### Kasus C
Setelah perilisan arsitektur micro-frontend baru, volume perayapan Googlebot ke halaman `/checkout/*` meningkat 500%, sedangkan perayapan ke halaman katalog produk `/product/*` anjlok sebesar 70%. URL checkout seharusnya tidak diindeks dan sudah ditandai `Disallow: /checkout/` di `robots.txt`. 

*Pertanyaan*: Mengapa Googlebot tetap merayap URL tersebut meskipun sudah ada aturan `Disallow` di `robots.txt`, dan bagaimana pipeline deteksi anomali Anda dapat mendeteksi serta memvalidasi akar masalah teknis ini secara otomatis?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Kunci Jawaban Bagian 1 (Basic)
1. **B** — Penyerang dapat menyetel PTR record sembarang pada kontrol DNS IP mereka sendiri. Hanya fDNS (A lookup) balik ke domain otoritatif Google yang dapat membuktikan kepemilikannya.
2. **C** — GSC memiliki data latency signifikan (2-3 hari) serta memotong data secara sampling, tidak memadai untuk deteksi anomali instan.
3. **C** — `SummingMergeTree` secara otomatis mengakumulasi nilai-nilai numerik pada baris dengan primary key yang identik selama proses merge.
4. **B** — Partisi harian memicu pembuatan ribuan direktori partisi kecil yang menyebabkan error kritis *Too many parts in all data in table*.
5. **B** — `CF-Connecting-IP` adalah header otoritatif standar dari Cloudflare yang merepresentasikan koneksi klien asli.

#### Panduan Jawaban Bagian 2 (Intermediate)
1. Jika cache resolver terkompromi (keracunan DNS), penyerang dapat memetakan lookup balik domain Google ke IP bot malicious mereka, menyebabkan sistem menandai *bad bot* sebagai *verified Googlebot*, sehingga mereka dapat melewati layer proteksi rate-limit WAF.
2. Latensi HTTP web terdistribusi memiliki ekor panjang (*long-tail distribution*) dan tidak berdistribusi normal (non-Gaussian). Nilai *mean* tertutup oleh jutaan respons cepat, sementara metrik p95/p99 menangkap outlier performa buruk yang secara langsung menjadi parameter Googlebot dalam menurunkan *crawl budget*.
3. Lonjakan drastis pada volume perayapan harian yang berbanding terbalik dengan variasi URL unik (misal: jutaan request merayap ke kombinasi query string parameter baru), serta tingginya rasio response 200 OK dengan panjang payload (Content-Length) yang seragam.
4. Karena verifikasi DNS membutuhkan I/O eksternal (meskipun ter-cache), proses ini memiliki karakteristik latensi fluktuatif. Memisahkannya menjaga *ClickHouse Sink Consumer* tetap dapat memproses ingest batch berkecepatan tinggi tanpa terhambat oleh *blocking DNS resolution*.
5. *Infrastructure failure* ditandai dengan lonjakan status code 5xx, penurunan mendadak pada seluruh cluster URL secara simultan, dan korelasi langsung dengan kenaikan TTFB. Penurunan perayapan akibat *Google Quality Algorithm* biasanya terisolir pada sub-cluster URL tertentu (misal: kategori produk tipis konten) sementara TTFB origin tetap normal.

#### Panduan Solusi Bagian 3 (Production Scenarios)
- **Kasus A**:
  - *Mitigasi Cepat*: Tingkatkan alokasi partisi Kafka dan scale worker pod Go secara horizontal (HPA). Aktifkan bypass verifikasi FCrDNS sementara jika IP telah berada di subnet tepercaya (CIDR cache fallback).
  - *Optimasi Permanen*: Ganti native Go DNS resolver biasa dengan implementasi non-blocking asynchronous DNS pool (misal: `miekg/dns` berbasis epoll) dan perbesar kapasitas L1 cache (Ristretto) untuk meminimalkan ketergantungan network roundtrip DNS.
- **Kasus B**:
  - Konfigurasi ClickHouse *Storage Policy* dengan dua volume: `hot` (NVMe) dan `cold` (Object Storage / S3).
  - Pindahkan partisi data `is_verified = 0` langsung ke storage `cold` setelah 3 hari menggunakan syntax `TTL event_timestamp + INTERVAL 3 DAY TO VOLUME 'cold'`.
  - Pasang TTL penghapusan permanen untuk log non-verified pada 14 hari, sementara log bot terverifikasi (`is_verified = 1`) dipertahankan selama 90 hari di disk NVMe.
- **Kasus C**:
  - Aturan `Disallow` di `robots.txt` hanya melarang perayapan, **bukan** melarang pengindeksan jika Googlebot menemukan URL tersebut dari tautan lain. Kemungkinan tim micro-frontend mengekspos tautan link fisik (`<a href="/checkout/...">`) di navigasi global/header halaman secara telanjang (tanpa rel="nofollow").
  - Anomaly engine mendeteksi ini dari kemunculan referer URL produk pada perayapan checkout, atau lonjakan status 200 pada URI cluster `/checkout` yang berkolerasi dengan penambahan release tag git deployment baru. Mitigasi: Perbaiki markup navigasi, ganti tag link checkout menjadi dynamic button click handlers, dan tambahkan header `X-Robots-Tag: noindex`.

---

### 16. Summary
- Pemantauan log *real-time* merupakan instrumen tingkat tertinggi dalam rekayasa SEO teknis modern; sistem ini melampaui batasan visibilitas analitik web konvensional (GA4) dan keterlambatan pelaporan Google Search Console.
- Keaslian bot mesin pencari **wajib divalidasi** menggunakan mekanisme deterministik **Forward-Confirmed Reverse DNS (FCrDNS)** dengan arsitektur *tiered cache* guna mengeliminasi serangan pemalsuan identitas (*bot spoofing*) tanpa mengorbankan performa *hot-path* server.
- Arsitektur berbasis **ClickHouse (OLAP)** yang dipadukan dengan **Apache Kafka** memungkinkan penanganan miliaran baris log secara hemat disk (kompresi ZSTD) serta memberikan metrik agregasi instan untuk melacak degradasi *Time to First Byte* (TTFB) dan distorsi alokasi *crawl budget*.
- Algoritma time-series statistika tingkat lanjut seperti **S-H-ESD** dan **CUSUM** memungkinkan tim rekayasa mengidentifikasi anomali perayapan dan memitigasi dampak pembaruan algoritma penelusuran (*Search Engine Core Update*) secara proaktif sebelum berdampak fatal pada trafik organik platform.