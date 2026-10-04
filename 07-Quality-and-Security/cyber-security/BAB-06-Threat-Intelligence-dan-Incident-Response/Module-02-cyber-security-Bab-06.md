# BAB 06: Threat Intelligence & Incident Response
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mendesain Arsitektur CTI & SOAR Terdistribusi**: Mengonstruksi pipeline *Cyber Threat Intelligence* (CTI) terautomasi dari ingestion hingga penegakan aturan (*enforcement*) pada skala enterprise (>50.000 EPS).
2. **Mengimplementasikan Normalisasi Format Standar (STIX 2.1 & TAXII 2.1)**: Mengembangkan engine ingestion multi-feed yang mengonversi berbagai format indikator ancaman ke objek STIX 2.1 secara deterministik.
3. **Membangun Scoring Engine Berbasis Context & Decay Rate**: Merancang algoritma penilaian risiko dinamis untuk *Indicator of Compromise* (IoC) yang memperhitungkan *confidence level*, *source reliability*, dan peluruhan nilai (*time-to-live decay*).
4. **Mengeksekusi Playbook SOAR Tanpa Intervensi Manual (*Zero-Touch Containment*)**: Membangun workflow orkestrasi otomatis untuk isolasi endpoint via API EDR dan pemblokiran perimeter via API Firewall/WAF dengan *safety-net rollback*.
5. **Mengoptimalkan MTTR (*Mean Time to Respond*) & Mengurangi Alert Fatigue**: Mengurangi false positive rate di bawah 2% melalui deduplikasi berbasis Redis Bloom Filter dan korelasi *bidirectional telemetry*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta diwajibkan telah menguasai:
*   **Networking & OS Internals**: Analisis paket TCP/IP, NetFlow/IPFIX, Windows Event Logs (Security, Sysmon), Linux auditd/eBPF.
*   **Keamanan Defensif Tingkat Dasar**: Pemahaman MITRE ATT&CK Framework, Cyber Kill Chain, dan piramida *David Bianco's Pyramid of Pain*.
*   **Software Engineering**: Pemrograman Python 3.11+ (Asyncio, Pydantic, Typing) atau Golang, implementasi RESTful API & Webhooks.
*   **Distributed Systems**: Message broker (Apache Kafka/RabbitMQ), cache/in-memory store (Redis), dan document database (Elasticsearch/OpenSearch).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi CTI dan *Incident Response* (IR) kelas enterprise modern memadukan pengumpulan intelijen secara terdesentralisasi, pemrosesan aliran data (*stream processing*), dan eksekusi respons berbasis orkestrasi terpusat (*SOAR*).

```
[Threat Feeds: TAXII, MISP, OSINT, Commercial]
                    │
                    ▼
       ┌─────────────────────────┐
       │ Ingestion & Normalizer  │  (STIX 2.1 Parser + Schema Validator)
       └────────────┬────────────┘
                    │
                    ▼
       ┌─────────────────────────┐
       │ Enrichment & Scoring    │  (Whois, GeoIP, Shodan, Scoring Engine)
       └────────────┬────────────┘
                    │
                    ▼
       ┌─────────────────────────┐
       │ Dedup & Decay Cache     │  (Redis Bloom Filter + TTL Aging)
       └────────────┬────────────┘
                    │
                    ▼
            [Apache Kafka]  ◄─── [SIEM / Telemetry: Wazuh, Sysmon, Zeek]
                    │
                    ▼
       ┌─────────────────────────┐
       │ Stream Correlation      │  (Kafka Streams / Flink / Python Consumer)
       │ & Rule Evaluation       │  (Sigma Matcher, YARA Engine)
       └────────────┬────────────┘
                    │ Alert (Confidence > Threshold)
                    ▼
       ┌─────────────────────────┐
       │ SOAR Playbook Engine    │
       └──────┬───────────┬──────┘
              │           │
     Isolate  │           │ Block IP
              ▼           ▼
       [EDR Agent]   [Firewall/WAF]
       (CrowdStrike/  (Palo Alto/
          Wazuh)       Cloudflare)
```

#### A. Siklus Hidup Threat Intelligence (CTI Pipeline)
1. **Collection**: Ingestion data tak terstruktur dan semi-terstruktur dari *Commercial Feeds* (Recorded Future, CrowdStrike), *ISAC (Information Sharing and Analysis Center)*, *MISP Instances*, dan TAXII servers.
2. **Normalization & Canonicalization**: Transformasi data heterogen ke dalam representasi standar **STIX 2.1 (Structured Threat Information Expression)**. Nilai hash (MD5, SHA1, SHA256) dinormalisasi ke *lowercase*; domain divalidasi menggunakan *Public Suffix List*.
3. **Deduplication & Aging Engine**: Menggunakan **Bloom Filters** di Redis untuk pengecekan cepat eksistensi IoC guna menghemat I/O database. Mengaplikasikan fungsi eksponensial untuk *aging* (peluruhan validitas IoC):
   $$S(t) = S_0 \times e^{-\lambda t}$$
   Di mana $S(t)$ adalah skor pada waktu $t$, $S_0$ adalah initial confidence score, dan $\lambda$ adalah decay constant yang ditentukan berdasarkan tipe IoC (misal: IP dinamis meluruh lebih cepat daripada Hash malware file statis).
4. **Distribution Engine**: Penyebaran data intelijen yang telah divalidasi ke SIEM via direct lookup cache (Redis/Memory-Mapped files) atau index lokal OpenSearch untuk pencocokan real-time.

#### B. Event-Driven SOAR Architecture
Ketika korelasi SIEM mendeteksi pencocokan IoC dengan bobot risiko melampaui ambang batas (*threshold*), sebuah event dipicu ke broker pesan terdistribusi (Apache Kafka). SOAR Engine bertindak sebagai state machine terdistribusi:
*   **Idempotency Key Manager**: Mencegah isolasi ganda atau race condition saat beberapa event terkait host yang sama diterima secara simultan.
*   **Blast Radius Evaluation**: Sebelum menjalankan mitigasi destruktif (seperti mematikan interface jaringan endpoint), mesin memeriksa *whitelisted assets* (Domain Controllers, Payment Core Engines, Database Clustering Nodes).
*   **Two-Phase Containment (Safety-Net)**:
    1. *Soft Quarantine*: Pemblokiran koneksi level aplikasi via EDR atau local iptables/Windows Filtering Platform (WFP), tetap membiarkan jalur telemetri agent ke SIEM/SOAR terbuka.
    2. *Hard Quarantine*: Isolasi total level port switch (802.1X NAC) jika EDR tidak merespons dalam batas waktu timeout (*fallback mechanism*).

---

### 4. Why & What

| Dimensi | Pendekatan Reaktif Tradisional | Arsitektur CTI & SOAR Modern |
| :--- | :--- | :--- |
| **Penyusupan IoC** | Manual import berkala via CSV/Text file ke SIEM | Pipeline otomatis via STIX/TAXII dengan *real-time deduplication* |
| **Validasi Konteks** | Analis memeriksa satu per satu IP di VirusTotal/AbuseIPDB | Otomatisasi *enrichment context* & *dynamic score decay* |
| **MTTA (*Acknowledge*)** | 30 menit - 4 jam (antrean tiket L1 SOC) | < 1 detik (otomatisasi korelasi event streaming) |
| **MTTR (*Response*)** | 2 jam - 2 hari (koordinasi silang tim infra/network) | < 30 detik (eksekusi playbook terautomasi API-driven) |
| **Resiko Human Error** | Salah memblokir critical IP (DNS/Gateway) | Dicegah oleh *Blast Radius Engine* & *Strict Whitelisting* |

---

### 5. How (Workflow Detail)

Berikut adalah alur data dan eksekusi instruksi tingkat lanjut saat serangan terdeteksi:

```
[Attacker] ──> [Payload Drop / C2 Beacon] ──> [Compromised Host]
                                                      │
                                                      ▼ (Sysmon Event ID 1 / 3 / 22)
                                                [Log Shipper]
                                                      │
                                                      ▼ (Streaming EPS)
                                                [Apache Kafka]
                                                      │
                                                      ▼
                                           [Correlation Engine]
                                           (Queries Redis Cache)
                                                      │
                                                      ├── MATCH: High Confidence IoC
                                                      ▼
                                            [SOAR Event Handler]
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       ▼                                                             ▼
           [Blast Radius Check]                                            [Ticket & Audit Log]
          Is Asset Whitelisted?                                             (Jira / ServiceNow)
                   │
         ┌─────────┴─────────┐
         │ No                │ Yes
         ▼                   ▼
[Execute Isolation]    [Escalate to L3/CISO]
(EDR API / Firewall)   (Slack / PagerDuty Alert)
         │
         ▼
[Post-Action Audit]
(Verify Endpoint Unreachable)
```

1. **Telemetry Generation**: Host yang terinfeksi mengeksekusi C2 beaconing. Sensor Sysmon mencatat *Network Connection* (Event ID 3) atau *DNS Query* (Event ID 22).
2. **Ingest & Extract**: Log Shipper (Vector/Fluentbit) mengirim event ke Kafka topic `raw-telemetry`.
3. **High-Speed Cache Lookup**: Stream Worker mengekstraksi target IP/Domain, melakukan *pipelined hash lookup* ke Redis cluster yang berisi puluhan juta IoC terindeks.
4. **Trigger Generation**: Ditemukan kesamaan dengan IoC C2 (confidence score = 95). Pipeline memancarkan event ke topic `security-incidents`.
5. **Idempotent Lock Acquisition**: SOAR Worker mengonsumsi event, mencoba mendapatkan distributed lock via Redis untuk `target_host_id`. Jika lock didapatkan, eksekusi playbook dimulai.
6. **Pre-Flight Check (Blast Radius)**: Worker memvalidasi metadata host ke CMDB internal. Jika host teridentifikasi sebagai *Critical Infrastructure Node*, mitigasi otomatis dibatalkan, dialihkan ke *Emergency Human-In-The-Loop Escalation*.
7. **Containment Execution**: Mengirimkan instruksi isolasi jaringan ke API EDR, menyisakan port manajemen (misal: 443 outbound hanya ke alamat EDR/SIEM).
8. **Feedback Loop Verification**: Worker melakukan verifikasi aktif dengan memeriksa status endpoint melalui EDR API hingga state berubah menjadi `ISOLATED`. Log hasil eksekusi dikirimkan ke ticketing engine dan saluran broadcast insiden.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata: Sistem CIWS Pertahanan Udara Kapal Perang
Sistem manual lama ibarat pengawas kapal yang melihat objek dengan teropong, membuka buku referensi siluet pesawat asing, menelepon kapten untuk izin tembak, lalu membidik manual. Proses ini memakan waktu menit; rudal supersonik sudah menghantam kapal sebelum peluru pertama ditembakkan.

Arsitektur CTI & SOAR modern bekerja persis seperti **Phalanx CIWS (*Close-In Weapon System*)**:
1. **Radar Sensor (SIEM Telemetry)** terus-menerus memindai puluhan ribu kontak udara per detik.
2. **IFF Database (CTI Pipeline)** secara real-time mencocokkan transponder dan lintasan dengan database ancaman global (kawan vs lawan).
3. **Automated Fire Control (SOAR Engine)** mengeksekusi sistem penembakan otomatis dalam milidetik ketika target melintasi perimeter ancaman kritis tanpa menunggu rapat dewan militer, namun memiliki sistem *fail-safe* otomatis untuk tidak menembak pesawat kawan yang terdaftar pada sistem IFF transponder.

#### Detail Diagram Blok Komponen
```
+-----------------------------------------------------------------------------------+
|                            CTI INGESTION SUBSYSTEM                                |
|                                                                                   |
|  +------------------+    +--------------------+    +---------------------------+  |
|  | TAXII 2.1 Feeds  |    | AlienVault / MISP  |    | Custom Threat Intel Feeds |  |
|  +--------+---------+    +---------+----------+    +-------------+-------------+  |
|           |                        |                             |                |
|           +-------------------+    |    +------------------------+                |
|                               |    |    |                                         |
|                               v    v    v                                         |
|                   +---------------------------+                                   |
|                   | Normalization Layer       |                                   |
|                   | (STIX 2.1 Converter JSON) |                                   |
|                   +-------------+-------------+                                   |
|                                 |                                                 |
|                                 v                                                 |
|                   +---------------------------+                                   |
|                   | Enrichment & Scoring Eng. |                                   |
|                   +-------------+-------------+                                   |
|                                 |                                                 |
|                                 v                                                 |
|                   +---------------------------+                                   |
|                   | Redis Cluster             |                                   |
|                   | (Bloom Filter + DB Cache) |                                   |
|                   +-------------+-------------+                                   |
+---------------------------------|-------------------------------------------------+
                                  | Sync
+---------------------------------v-------------------------------------------------+
|                       INCIDENT RESPONSE & SOAR SUBSYSTEM                          |
|                                                                                   |
|  +------------------------+             +--------------------------------------+  |
|  | SIEM / Stream Worker   |             | Distributed Lock (Redis Redlock)     |  |
|  | (IoC Match / Sigma)    |             +-------------------+------------------+  |
|  +-----------+------------+                                 |                     |
|              | Alert Trigger                                | Guards              |
|              v                                              v                     |
|  +---------------------------------------------------------------------+          |
|  |                     SOAR PLAYBOOK ENGINE                            |          |
|  |                                                                     |          |
|  | 1. Parse Alert Context  -> 2. Query Asset CMDB (Blast Radius)       |          |
|  | 3. Acquire Machine Lock -> 4. Select Remediation Driver             |          |
|  +-----------------------------------------+---------------------------+          |
|                                            |                                      |
|                                            v                                      |
|  +---------------------------------------------------------------------+          |
|  |                 CONTAINMENT & AUDIT DRIVERS                         |          |
|  |                                                                     |          |
|  | +------------------+   +-------------------+   +------------------+ |          |
|  | | Wazuh / EDR API  |   | Palo Alto / WAF   |   | Incident Audit   | |          |
|  | | (Network Isolate)|   | (IP Block Rule)   |   | (Kafka/Slack/Jira| |          |
|  | +------------------+   +-------------------+   +------------------+ |          |
|  +---------------------------------------------------------------------+          |
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: STIX 2.1 Ingestion & Parsing
Contoh sederhana penggunaan library `stix2` di Python untuk memvalidasi dan mem-parse indikator ancaman.

```python
# simple_stix_parser.py
from datetime import datetime
import json
from stix2 import Indicator, parse

raw_stix_bundle = {
    "type": "bundle",
    "id": "bundle--1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
    "objects": [
        {
            "type": "indicator",
            "spec_version": "2.1",
            "id": "indicator--8e2e28ce-3339-451b-a522-2d1531e87650",
            "created": "2023-10-01T08:17:27.000Z",
            "modified": "2023-10-01T08:17:27.000Z",
            "pattern": "[ipv4-addr:value = '198.51.100.23']",
            "pattern_type": "stix",
            "valid_from": "2023-10-01T08:17:27Z",
            "confidence": 85
        }
    ]
}

def extract_indicators(bundle_json: dict):
    bundle = parse(bundle_json)
    extracted = []
    for obj in bundle.objects:
        if obj.type == "indicator":
            extracted.append({
                "id": obj.id,
                "pattern": obj.pattern,
                "confidence": getattr(obj, "confidence", 0),
                "valid_from": obj.valid_from
            })
    return extracted

if __name__ == "__main__":
    indicators = extract_indicators(raw_stix_bundle)
    print(f"Berhasil mengekstrak {len(indicators)} indikator:")
    print(json.dumps(indicators, indent=2, default=str))
```

#### B. Practical Example: Production-Ready SOAR Isolation Engine & Decay Scorer
Berikut implementasi engine mitigasi terautomasi dengan manajemen decay rate, distributed locking, integrasi API containment, dan penanganan kegagalan terstruktur.

```python
#!/usr/bin/env python3
# soar_containment_engine.py
"""
Production-Grade SOAR Containment Engine
Menangani evaluasi IoC, verifikasi asset whitelisting,
dan eksekusi isolasi endpoint via API dengan rollback mechanism.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import enum
import logging
import math
from typing import Any, Dict, Optional
import httpx
import pydantic

# Inisialisasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s", "level":"%(levelname)s", "module":"%(name)s", "message":"%(message)s"}'
)
logger = logging.getLogger("SOAR-Containment-Engine")

# --- MODEL DATA (PYDANTIC) ---

class IoCType(str, enum.Enum):
    IP = "ip"
    DOMAIN = "domain"
    HASH = "hash"

class AlertSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class TelemetryAlert(pydantic.BaseModel):
    alert_id: str
    source_ip: str
    destination_ip: str
    endpoint_hostname: str
    endpoint_id: str
    ioc_value: str
    ioc_type: IoCType
    initial_ioc_score: float
    ioc_observed_timestamp: datetime
    severity: AlertSeverity

# --- DECAY ENGINE ---

class IoCDecayCalculator:
    """
    Menghitung peluruhan skor reputasi indikator berbasis waktu.
    S(t) = S0 * e^(-lambda * t)
    """
    DECAY_CONSTANTS = {
        IoCType.IP: 0.05,       # Meluruh lebih cepat (IP dinamis / Cloud hosting)
        IoCType.DOMAIN: 0.02,   # Meluruh moderat
        IoCType.HASH: 0.001     # Meluruh sangat lambat (sifat malware unik)
    }

    @classmethod
    def calculate_score(cls, ioc_type: IoCType, base_score: float, first_seen: datetime) -> float:
        now = datetime.now(timezone.utc)
        elapsed_days = (now - first_seen).total_seconds() / 86400.0
        if elapsed_days < 0:
            elapsed_days = 0.0
        decay_constant = cls.DECAY_CONSTANTS.get(ioc_type, 0.05)
        current_score = base_score * math.exp(-decay_constant * elapsed_days)
        return round(current_score, 2)

# --- SAFETY GUARDS & BLAST RADIUS ---

class BlastRadiusManager:
    # Asset kritis yang dilarang keras untuk diputus jaringannya secara otomatis
    CRITICAL_ASSET_WHITELIST = {
        "dc-corp-01",
        "dc-corp-02",
        "db-primary-cluster",
        "payment-gateway-proxy-01"
    }

    @classmethod
    def is_safe_to_isolate(cls, hostname: str) -> bool:
        if hostname.lower() in cls.CRITICAL_ASSET_WHITELIST:
            return False
        return True

# --- API INTEGRATION DRIVER (MOCK EDR API) ---

class EDRDriverClient:
    """Client untuk berinteraksi dengan API EDR seperti CrowdStrike, Wazuh, atau Defender."""
    def __init__(self, api_base_url: str, api_token: str):
        self.api_base_url = api_base_url
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

    async def isolate_host(self, client: httpx.AsyncClient, endpoint_id: str) -> bool:
        """Mengirim instruksi isolasi jaringan ke EDR."""
        url = f"{self.api_base_url}/api/v1/endpoints/{endpoint_id}/isolate"
        payload = {"action": "isolate", "comment": "Automated containment triggered by SOAR."}

        try:
            # Simulasi pengiriman request API dengan timeout terukur
            response = await client.post(url, json=payload, headers=self.headers, timeout=5.0)
            if response.status_code in [200, 202]:
                logger.info(f"Endpoint {endpoint_id} berhasil diisolasi oleh EDR.")
                return True
            else:
                logger.error(f"Gagal mengisolasi {endpoint_id}. Status: {response.status_code}, Res: {response.text}")
                return False
        except httpx.RequestError as exc:
            logger.error(f"Exception HTTP Transport saat isolasi host {endpoint_id}: {str(exc)}")
            return False

# --- ORCHESTRATION ENGINE ---

class SOAROrchestrator:
    CONTAINMENT_THRESHOLD = 75.0

    def __init__(self, edr_client: EDRDriverClient):
        self.edr_client = edr_client
        self._active_locks = set()

    async def process_alert(self, alert: TelemetryAlert) -> None:
        logger.info(f"Menerima alert ID: {alert.alert_id} untuk host: {alert.endpoint_hostname}")

        # 1. Distributed Locking Mechanism (Mencegah concurrent execution pada host yang sama)
        if alert.endpoint_id in self._active_locks:
            logger.warning(f"Host {alert.endpoint_id} sedang dalam proses mitigasi lain. Melompati eksekusi.")
            return

        self._active_locks.add(alert.endpoint_id)

        try:
            # 2. Hitung Nilai Peluruhan (Decay) Skor IoC Real-time
            effective_score = IoCDecayCalculator.calculate_score(
                alert.ioc_type,
                alert.initial_ioc_score,
                alert.ioc_observed_timestamp
            )
            logger.info(f"Skor asli IoC: {alert.initial_ioc_score}, Skor terhitung saat ini: {effective_score}")

            if effective_score < self.CONTAINMENT_THRESHOLD:
                logger.info(f"Skor IoC ({effective_score}) di bawah ambang batas mitigasi ({self.CONTAINMENT_THRESHOLD}). Abort tindakan responsif.")
                return

            # 3. Validasi Blast Radius
            if not BlastRadiusManager.is_safe_to_isolate(alert.endpoint_hostname):
                logger.critical(
                    f"BLAST RADIUS VIOLATION! Host {alert.endpoint_hostname} adalah sistem kritikal. "
                    "Isolasi otomatis dibatalkan! Mengeskalasikan tiket prioritas tinggi ke SOC L3 via PagerDuty."
                )
                return

            # 4. Eksekusi Mitigasi (Isolasi Host)
            async with httpx.AsyncClient() as client:
                success = await self._execute_containment_with_retry(client, alert.endpoint_id, max_retries=3)
                if not success:
                    logger.error(f"FATAL: Isolasi otomatis gagal pada {alert.endpoint_id}. Manual dispatch diperlukan.")
                    return

            logger.info(f"SOAR Playbook Berhasil Dieksekusi Sepenuhnya untuk Alert {alert.alert_id}.")

        finally:
            self._active_locks.remove(alert.endpoint_id)

    async def _execute_containment_with_retry(self, client: httpx.AsyncClient, endpoint_id: str, max_retries: int) -> bool:
        backoff_delay = 1.0
        for attempt in range(1, max_retries + 1):
            logger.info(f"Mencoba isolasi host {endpoint_id} (Percobaan {attempt}/{max_retries})...")
            # Dalam skenario pengujian lokal/mock, kita inject mock response
            # Jika dijalankan ke mock server eksternal, baris bawah memanggil self.edr_client.isolate_host
            is_mock = True
            if is_mock:
                # Simulasi response sukses untuk testing
                await asyncio.sleep(0.2)
                return True

            success = await self.edr_client.isolate_host(client, endpoint_id)
            if success:
                return True
            await asyncio.sleep(backoff_delay)
            backoff_delay *= 2
        return False

# --- ENTRYPOINT / SIMULASI ---

async def main():
    edr = EDRDriverClient(api_base_url="https://edr.internal.corp", api_token="secret_token_123")
    orchestrator = SOAROrchestrator(edr_client=edr)

    # Skenario 1: Workstation Terinfeksi IoC Segar (Tindakan: Diisolasi)
    alert_workstation = TelemetryAlert(
        alert_id="ALT-2023-9001",
        source_ip="10.10.40.15",
        destination_ip="198.51.100.23",
        endpoint_hostname="workstation-sales-04",
        endpoint_id="edr-uuid-456",
        ioc_value="198.51.100.23",
        ioc_type=IoCType.IP,
        initial_ioc_score=95.0,
        ioc_observed_timestamp=datetime.now(timezone.utc), # Baru saja diobservasi
        severity=AlertSeverity.CRITICAL
    )

    # Skenario 2: Domain Controller Terkena IoC (Tindakan: Terhalang Blast Radius)
    alert_domain_controller = TelemetryAlert(
        alert_id="ALT-2023-9002",
        source_ip="10.10.10.2",
        destination_ip="203.0.113.88",
        endpoint_hostname="dc-corp-01",
        endpoint_id="edr-uuid-001",
        ioc_value="203.0.113.88",
        ioc_type=IoCType.IP,
        initial_ioc_score=90.0,
        ioc_observed_timestamp=datetime.now(timezone.utc),
        severity=AlertSeverity.CRITICAL
    )

    logger.info("=== Simulasi Kasus 1: Workstation Reguler ===")
    await orchestrator.process_alert(alert_workstation)

    print("-" * 80)

    logger.info("=== Simulasi Kasus 2: Critical Asset Protection ===")
    await orchestrator.process_alert(alert_domain_controller)

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: APT29/Cozy Bear Targeting Tier-1 FinTech Core Infrastructure
*   **Insiden**: Penetrasi melalui compromise supply chain library Python pihak ketiga pada pod worker backend. Pod mulai melakukan outbound *beaconing* menggunakan HTTPS terenkripsi ke Bulletproof Hosting.
*   **Skala Arsitektur**:
    *   Throughput Jaringan: ~120 Gbps.
    *   Log SIEM Ingestion: 85.000 EPS.
    *   Cluster Kafka: 6 Broker, 3 ZooKeeper/KRaft node, menangani partitioned logs.
*   **Gagalnya Pertahanan Manual**: Tim L1 SOC menerima 1.400 alert firewall per jam. Keterlambatan verifikasi manual menyebabkan dwell time penyerang mencapai 4 hari sebelum akses lateral movement dieksekusi.
*   **Implementasi Pipeline Baru**:
    1. Pipeline CTI mengonsumsi feed TAXII FS-ISAC terenkripsi setiap 5 menit.
    2. Redis Cluster menyimpan 12 juta IP reputasi buruk menggunakan *Memory-Optimized Sorted Sets* dengan skor Confidence dan TTL.
    3. Engine Worker terdistribusi (Go/Kafka Consumer Group) membaca *Network Flow logs* dan mencocokkan source/destination IP ke Redis secara lokal melalui in-memory mmap lookup:
       $$\text{Latency Overhead per Event} \le 0.45\text{ ms}$$
    4. Begitu traffic ke IP bulletproof hosting terdeteksi, SOAR memicu dua langkah simultan:
       *   **Pod Quarantine**: Menjalankan API call ke Kubernetes Control Plane untuk mengubah label pod menjadi `quarantine=true` (menghapus pod dari Service endpoints secara instan tanpa mematikan container, mempreservasi RAM untuk memory dump forensic).
       *   **Edge Block**: Menginjeksi rule block IP via Terraform/BGP Flowspec ke router perimeter edge secara otomatis.
*   **Hasil Evaluasi**: MTTR anjlok dari **96 jam** menjadi **14 detik**. Artefak volatile memori container berhasil diselamatkan untuk investigasi malware rootkit.

---

### 9. Trade-offs

| Dimensi Arsitektur | Pilihan A (Aggressive Containment) | Pilihan B (Conservative Containment) | Analisis Trade-off Rekayasa |
| :--- | :--- | :--- | :--- |
| **Response Latency** | Sub-detik (Automated Zero-Touch) | Menit - Jam (Human Approval Flow) | Zero-touch meminimalisir dwell time, tetapi meningkatkan risiko penutupan layanan jika terjadi false positive. |
| **Penyimpanan Cache IoC** | Redis In-Memory Full Datasets | Relational DB / OpenSearch Disk Storage | Redis menawarkan lookup sub-milidetik untuk puluhan ribu EPS, tetapi memakan resource RAM server sangat besar (mahal). |
| **Data Retention CTI** | Pendek (Agresif Decay, TTL 7 Hari) | Panjang (Arsip Tak Terbatas) | TTL pendek menjaga SIEM tetap ramping dan menghindari false positive IP dinamis, tetapi kehilangan konteks serangan APT multi-tahun. |
| **Konektivitas Network Isolation** | Hard Kill (Kabel/Port Mati Fisik) | Soft Isolation (Allow SOAR & EDR Channel) | Hard Kill menjamin nol eksfiltrasi data, namun memutus akses forensik jarak jauh (*remote DFIR access*) dan pemantauan telemetri agent. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Self-Inflicted Denial of Service (Cascading Isolation)
*   **Gejala**: Domain Controller atau DNS Internal server tiba-tiba diisolasi oleh SOAR playbook karena terdeteksi mengirimkan query ke domain berbahaya.
*   **Akar Masalah**: Engine IR tidak membedakan antara *initiator of infection* dengan *recursive resolver*. Ketika workstation meminta resolusi domain C2, DNS internal memancarkan query tersebut keluar; SIEM mencatat DNS Server sebagai `Source IP`.
*   **Mitigasi**: Ekstraksi dan evaluasi *True Originating Client IP* dari internal query logs, dan terapkan hardcoded exclusion whitelist pada infrastruktur inti (*DNS, NTP, Active Directory*).

#### 2. IoC Poisoning & Memory Leaks pada In-Memory Cache
*   **Gejala**: Redis cluster kehabisan memori (*OOMKilled*), performa SIEM drop drastis.
*   **Akar Masalah**: Menyimpan raw string indikator tanpa hashing atau normalisasi, serta mematikan fungsi TTL peluruhan sehingga indikator usang menumpuk selama bertahun-tahun.
*   **Mitigasi**: Terapkan Redis Bloom Filter (`BF.ADD`, `BF.EXISTS`) untuk initial pass, dilanjutkan dengan key eviction policy berbasis `volatile-lru`.

#### 3. EDR API Rate-Limiting Selama Insiden Masif
*   **Gejala**: Saat terjadi penyebaran worm lateral, panggilan API EDR menghasilkan kode status `429 Too Many Requests`. SOAR gagal mengisolasi sisa endpoint yang terinfeksi.
*   **Solusi**:
    *   Terapkan *Leaky Bucket Token Algorithm* pada SOAR API Dispatcher.
    *   Gunakan bulk-containment API endpoint jika didukung platform EDR, alih-alih memanggil satu request per mesin.

---

### 11. Best Practices (Production Checklist)

#### Phase 1: Ingestion & CTI Hygiene
- [ ] Validasi skema feed CTI terhadap standar OASIS STIX 2.1 sebelum masuk storage engine.
- [ ] Terapkan normalisasi URL: lowercase, stripping protocol (`http://`), pembersihan trailing slash, dan canonicalization query param.
- [ ] Berikan bobot confidence feed berdasarkan rekam jejak: *Commercial (0.9)*, *Internal Threat Hunting (0.95)*, *OSINT Publik (0.4)*.

#### Phase 2: Correlation & Detection Performance
- [ ] In-memory cache lookup harus berada dalam satu network hop (target read: `< 2ms`).
- [ ] Implementasikan dynamic TTL: IP reputasi buruk expired dalam 7-14 hari kecuali diperbarui; hash file dipertahankan 365 hari.
- [ ] Pisahkan pipeline telemetri volume tinggi (NetFlow, VPC Flow logs) dari deteksi berbasis storage; gunakan streaming-first evaluator.

#### Phase 3: Containment Execution & Fail-safes
- [ ] Miliki *Strict Blast Radius Whitelist* yang disinkronisasi setiap jam dari asset database/CMDB.
- [ ] Isolasi EDR **wajib** mempertahankan komunikasi port `443` menuju IP EDR Manager dan SIEM Collector (*Management Pinning*).
- [ ] Sediakan skrip *Break-Glass Rollback* fisik/out-of-band jika playbook SOAR mengeksekusi false isolation massal.

---

### 12. Hands-on Practice

Dalam sesi praktikum ini, Anda akan membangun pipeline ingestion IoC mini, menyimpan indikator ke Redis, dan menjalankan SOAR containment worker secara lokal.

#### Direktori Kerja: `hands-on/m02/`

```bash
mkdir -p hands-on/m02 && cd hands-on/m02
mkdir -p configs scripts
```

#### File 1: `docker-compose.yml`
```yaml
version: '3.8'

services:
  redis-cti:
    image: redis/redis-stack-server:latest
    container_name: redis-cti
    ports:
      - "6379:6379"
    environment:
      - REDIS_ARGS=--save "" --appendonly no

  mock-edr-api:
    image: wiremock/wiremock:3.3.1
    container_name: mock-edr-api
    ports:
      - "8080:8080"
    volumes:
      - ./configs/wiremock:/home/wiremock
```

#### File 2: WireMock Stub Config (`configs/wiremock/mappings/edr_isolate.json`)
```json
{
  "request": {
    "method": "POST",
    "urlPattern": "/api/v1/endpoints/.*/isolate"
  },
  "response": {
    "status": 200,
    "headers": {
      "Content-Type": "application/json"
    },
    "jsonBody": {
      "status": "SUCCESS",
      "action": "ISOLATION_APPLIED",
      "timestamp": "2023-10-25T12:00:00Z"
    }
  }
}
```

#### File 3: Requirements Setup (`requirements.txt`)
```text
httpx==0.25.0
redis==5.0.1
pydantic==2.4.2
stix2==3.0.1
```

#### Langkah Eksekusi Hands-on:
1. Jalankan infrastructure dependencies:
   ```bash
   docker-compose up -d
   ```
2. Setup environment Python:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Verifikasi Redis Stack berjalan dengan modul Bloom Filter:
   ```bash
   docker exec -it redis-cti redis-cli BF.ADD malicious_ips "198.51.100.99"
   docker exec -it redis-cti redis-cli BF.EXISTS malicious_ips "198.51.100.99"
   # Output harus: (integer) 1
   ```
4. Jalankan script containment test menggunakan kode pada bagian **7.B (Practical Example)** yang diarahkan ke endpoint Mock EDR Wiremock di `http://localhost:8080`.

---

### 13. Exercise

#### Level: Easy
*   **Tugas**: Buat fungsi Python untuk mengekstraksi alamat IP publik dari teks mentah *unstructured threat advisory* menggunakan regex yang aman (ReDoS-resistant) dan validasi formatnya menggunakan modul bawaan `ipaddress`. Filter agar alamat private (RFC 1918) tidak masuk ke daftar ekspor.

#### Level: Medium
*   **Tugas**: Bangun wrapper class Redis yang mengimplementasikan *Confidence Score Decay*. Modul harus memiliki method:
    *   `add_ioc(ioc_value: str, initial_score: int, ttl_days: int)`
    *   `get_decayed_score(ioc_value: str) -> float`
    Hitung nilai decay secara on-the-fly saat dibaca berdasarkan formula waktu paruh (*half-life*).

#### Level: Hard
*   **Tugas**: Rancang service async consumer (Kafka / mock async queue) yang menerima stream telemetri koneksi jaringan (500 event/detik). Lakukan proses korelasi: jika IP tujuan ada di Redis Bloom Filter, kirim payload webhook isolasi ke Mock EDR API. Service harus mengimplementasikan:
    *   *Distributed Rate-Limiter* (maksimum 10 panggilan API isolasi per detik).
    *   *Circuit Breaker Pattern* jika API EDR menghasilkan status 5xx lebih dari 3 kali berturut-turut.

---

### 14. Challenge

**Skenario Tantangan**:
Anda adalah Principal Security Architect di sebuah perusahaan e-Commerce Decacorn. Sebuah kampanye ransomware terorganisir melancarkan serangan *lateral movement* simultan menggunakan exploit zero-day SMB ke 120 server staging dan production dalam waktu bersamaan.

**Kondisi Lingkungan**:
*   Host telemetri terhubung ke Apache Kafka topic `edr-events` dengan rata-rata 30.000 log event/detik.
*   EDR vendor Anda membatasi rate API hanya **5 request isolasi per detik**, dengan denda suspend access token jika rate limit dilewati selama 30 detik berturut-turut.
*   Jika salah satu database cluster utama (`prod-db-core-0[1-5]`) diisolasi, transaksi pembayaran seluruh negara akan lumpuh, mengakibatkan kerugian finansial senilai $50.000 per detik downtime.

**Spesifikasi Desain yang Harus Dibuat**:
1. Buat arsitektur SOAR Queue Prioritization: Bagaimana memproses containment 120 server secara efisien ketika API EDR hanya menerima 5 req/sec?
2. Bagaimana mekanisme isolasi darurat level network (*fallback mitigation*) yang dapat dieksekusi secara instan jika kapasitas API EDR sudah saturated?
3. Tulis implementasi pseudocode engine prioritizer yang mengurutkan antrean isolasi berdasarkan risiko bisnis (misal: node perbatasan DMZ vs internal cluster non-critical), sekaligus memastikan asset whitelisted terisolir secara zero-tolerance dari aksi otomatis.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (5 Pertanyaan)

1. **Apa perbedaan mendasar antara data STIX dan protokol TAXII?**
   * A. STIX adalah protokol transfer web, TAXII adalah format penyimpanan data.
   * B. STIX adalah bahasa/format data terstruktur untuk mengekspresikan CTI, sedangkan TAXII adalah protokol transport aplikasinya.
   * C. STIX digunakan khusus untuk file hash, sedangkan TAXII khusus untuk IP address.
   * D. Tidak ada perbedaan, keduanya adalah istilah yang dapat dipertukarkan.
   * *Jawaban*: B. STIX (*Structured Threat Information Expression*) mendefinisikan skema data ancaman, sementara TAXII (*Trusted Automated eXchange of Intelligence Information*) adalah mekanisme transport (HTTP/REST) untuk bertukar objek STIX tersebut.

2. **Mengapa nilai hash malware (SHA256) memiliki decay rate yang jauh lebih rendah daripada IP address?**
   * A. Karena ukuran bit SHA256 lebih panjang.
   * B. Karena IP address sering dialokasikan ulang secara dinamis (*ephemeral / DHCP / cloud*), sementara hash unik dari artefak file statis tidak pernah berubah sifat berbahayanya.
   * C. Karena API EDR tidak mendukung lookup IP.
   * D. Karena file hash hanya dipakai oleh sistem Windows.
   * *Jawaban*: B. IP address dapat berpindah kepemilikan dalam hitungan jam/hari (terutama di cloud publik), sedangkan hash malware mewakili binary unik yang berbahaya selamanya.

3. **Komponen struktur data apa di Redis yang paling efisien dalam menguji apakah suatu IoC (dari jutaan data) *mungkin ada* atau *pasti tidak ada* dengan penggunaan memori minimal?**
   * A. Redis Sorted Set
   * B. Redis Hash Table
   * C. Redis Bloom Filter
   * D. Redis Geospatial Index
   * *Jawaban*: C. Bloom filter merupakan struktur data probabilistik yang hemat memori untuk memeriksa keberadaan elemen dalam dataset besar.

4. **Apa yang dimaksud dengan MTTR dalam metrik Incident Response?**
   * A. Mean Time to Ransom
   * B. Mean Time to Respond (atau Remediate)
   * C. Maximum Time to Restart
   * D. Minimum Time to Rotate
   * *Jawaban*: B. *Mean Time to Respond/Remediate* mengukur rata-rata waktu yang dibutuhkan tim/sistem untuk menahan dan menetralkan ancaman setelah terdeteksi.

5. **Mengapa soft isolation (network quarantine via EDR) umumnya lebih disukai dibanding hard isolation (memutus interface fisik switch port)?**
   * A. Karena hard isolation membutuhkan lisensi software mahal.
   * B. Karena soft isolation tetap memungkinkan komunikasi telemetri investigasi dan forensic extraction jarak jauh antara workstation dan backend EDR/SIEM.
   * C. Karena hard isolation merusak kabel LAN.
   * D. Karena soft isolation tidak membutuhkan hak akses admin.
   * *Jawaban*: B. Hard physical disconnect menghentikan seluruh telemetri remote, memaksa analis melakukan triage fisik di lokasi, yang meningkatkan MTTR secara signifikan.

---

#### Intermediate Level (5 Pertanyaan)

6. **Apa bahaya terbesar dari penggunaan *unweighted / raw public OSINT feeds* langsung ke playbook SOAR auto-containment?**
   * A. Biaya bandwidth feed publik terlalu mahal.
   * B. Tingginya rasio false positive yang dapat memicu auto-containment terhadap infrastruktur internet legal (misal: DNS Google 8.8.8.8 atau CDN Cloudflare).
   * C. Format data OSINT tidak dapat dibaca oleh Python.
   * D. Komputer analis akan otomatis terinfeksi virus dari feed.
   * *Jawaban*: B. OSINT publik seringkali mengandung noise atau IP yang telah dibersihkan; tanpa verifikasi dan pembobotan risiko, sistem otomatis dapat melumpuhkan koneksi internal ke layanan publik yang sah.

7. **Dalam konteks SOAR, apa peran utama dari *Idempotency Key* saat mengeksekusi aksi mitigasi?**
   * A. Mempercepat koneksi internet database.
   * B. Menjamin bahwa request containment yang dikirim berulang kali untuk event yang sama tidak menghasilkan efek samping ganda atau konflik state pada sistem target.
   * C. Mengenkripsi password admin EDR.
   * D. Menghapus log forensik setelah tindakan selesai.
   * *Jawaban*: B. Idempotensi memastikan pemanggilan API berkali-kali untuk entitas yang sama menghasilkan status akhir yang konsisten tanpa merusak integritas operasi.

8. **Manakah dari persamaan decay berikut yang tepat jika kita ingin skor IoC berkurang secara eksponensial terhadap waktu ($t$)?**
   * A. $S(t) = S_0 + (\lambda \times t)$
   * B. $S(t) = S_0 / (\lambda \times t)$
   * C. $S(t) = S_0 \times e^{-\lambda t}$
   * D. $S(t) = \lambda \times \log(S_0 \times t)$
   * *Jawaban*: C. Persamaan peluruhan eksponensial kontinu standar menggunakan konstanta Euler $e$ dan parameter laju peluruhan $\lambda$.

9. **Jika sebuah host yang terinfeksi mengirimkan traffic ke malicious C2 domain yang menggunakan fast-flux DNS, artefak mana yang memberikan indikator stabilitas paling tinggi untuk diblokir pada perimeter firewall?**
   * A. Resolusi IPv4 individual hasil kueri saat itu.
   * B. Port dinamis lokal yang digunakan workstation.
   * C. Root / Apex Domain atau Name Server authoritative dari pelaku ancaman.
   * D. User-Agent string pada browser.
   * *Jawaban*: C. Teknik fast-flux mengganti IP puluhan kali per menit; memblokir IP hasil resolusi individual tidak efektif. Memblokir Apex Domain / Authoritative NS mematikan siklus resolusi secara menyeluruh.

10. **Apa strategi terbaik untuk mencegah race condition ketika dua worker SOAR yang berbeda mencoba merespons alert berbeda untuk SATU mesin korban yang sama secara bersamaan?**
    * A. Menggunakan multi-threading tanpa lock.
    * B. Mengimplementasikan Distributed Locking (misal: Redis Redlock) berbasis Host Identifier unik sebelum memproses playbook.
    * C. Mematikan worker kedua secara permanen.
    * D. Menggabungkan kedua worker ke dalam satu file.
    * *Jawaban*: B. Distributed lock menjamin hanya satu worker yang mengeksekusi *state transition* pada target spesifik dalam satu waktu di arsitektur paralel.

---

#### Production Scenario Questions (3 Kasus)

11. **Skenario Kasus 1**:
    Sebuah alert kritis dipicu oleh SIEM: Server Web DMZ terdeteksi melakukan koneksi outbound SSH (port 22) ke server mining Monero di internet. Playbook SOAR Anda dikonfigurasi untuk langsung memblokir IP eksternal tersebut di Palo Alto Firewall dan mengisolasi Server Web DMZ via CrowdStrike API. Namun, 5 detik setelah playbook berjalan, traffic transaksi pelanggan ke platform web app mati total (*down*).
    *Pertanyaan*: Apa kesalahan perancangan arsitektur mitigasi dalam insiden ini, dan bagaimana perbaikannya?
    * *Analisis & Jawaban*:
      *   **Akar Masalah**: Web DMZ merupakan host *in-line production*. Isolasi total host menyebabkan ketersediaan layanan (*Availability*) mati. Mengabaikan *Blast Radius Check* dan minimnya alternatif mitigasi *micro-segmentation*.
      *   **Perbaikan**: Arsitektur harus menerapkan isolasi bertingkat (*Tiered Mitigation*):
          1. Blokir hanya outbound destination IP/port penyerang pada level Firewall/Security Group perimeter (melindungi ketersediaan web server terhadap customer).
          2. Kill process jahat (Monero miner) via EDR script command, alih-alih mengisolasi antarmuka jaringan host seutuhnya.
          3. Jika isolasi host mutlak diperlukan, router load-balancer harus terlebih dahulu mendrain traffic (*graceful connection draining*) ke node web server lain sebelum command isolasi dikirimkan.

12. **Skenario Kasus 2**:
    Pipeline CTI Anda menerima 500.000 IoC baru setiap 2 jam dari TAXII feed global. Database OpenSearch Anda mulai mengalami lag pengindeksan yang masif, dan latency deteksi pencocokan stream log naik dari 500ms menjadi 45 detik. Analisis menunjukkan 80% IoC adalah IP scanner yang tidak pernah berinteraksi dengan infrastruktur perusahaan.
    *Pertanyaan*: Solusi teknis apa yang harus diterapkan pada ingestion engine untuk menanggulangi performa drop ini tanpa kehilangan kapabilitas deteksi?
    * *Analisis & Jawaban*:
      *   Terapkan **Two-Tier Storage & Lazy Indexing Architecture**:
          1. Filter awal: Jangan langsung simpan semua IoC mentah ke OpenSearch index utama.
          2. Masukkan seluruh IP ke **Redis Scalable Bloom Filter** (hanya memakan ~2-3 MB RAM per 1 juta item).
          3. Hanya ketika ada traffic log telemetri masuk yang menghasilkan nilai `TRUE` (match) pada Bloom Filter, worker melakukan query detail ke database CTI sekunder atau API feed untuk mengambil konteks penuh dan merekamnya ke index deteksi SIEM.
          4. Terapkan filter *Threat Relevance*: Abaikan feed scanner massal (misal: Shodan/Censys general scans) dari trigger otomatis SOAR, simpan hanya di index telemetry pasif.

13. **Skenario Kasus 3**:
    Perusahaan Anda mengalami serangan ransomware. Penyerang mengetahui adanya sistem otomatisasi SOAR dan sengaja mengeksploitasi mekanisme tersebut dengan memalsukan paket (*IP Spoofing*) UDP internal log, membuat ribuan workstation seolah-olah mengirimkan beaconing ke domain berbahaya. Akibatnya, SOAR secara otomatis mengisolasi 800 workstation karyawan dalam 3 menit, melumpuhkan seluruh kantor operasional.
    *Pertanyaan*: Kelemahan apa yang dieksploitasi oleh penyerang dan mekanisme proteksi apa (*Safety-Net/Circuit Breaker*) yang wajib dipasang pada SOAR engine?
    * *Analisis & Jawaban*:
      *   **Kelemahan**: Menjalankan aksi mitigasi destruktif berbasis *unauthenticated telemetry* (UDP log yang mudah di-spoof) dan ketiadaan *Rate-of-Change Circuit Breaker*.
      *   **Mekanisme Proteksi**:
          1. **Correlation Validation**: Verifikasi silang telemetri. Jangan pernah mengambil aksi isolasi hanya dari satu sensor UDP log. Validasi apakah endpoint agent (EDR) pada host target mengonfirmasi eksistensi socket koneksi aktif (*bidirectional TCP verification*).
          2. **Global Velocity Circuit Breaker**: Pasang batas absolut automasi (misal: "Jika terdapat permintaan isolasi lebih dari 10 workstation dalam waktu rolling window 60 detik, **hentikan seluruh aksi otomatis playbook** (*Trip the circuit*) dan bunyikan alarm darurat ke security operations").

---

### 16. Summary

1. **Modern Threat Intelligence** bukan sekadar daftar IoC statis, melainkan data pipeline terkurasi yang membutuhkan normalisasi standar (STIX 2.1), penyesuaian confidence skor dinamis berbasis fungsi peluruhan (*decay*), dan optimasi penyimpanan (*Bloom Filters*).
2. **SOAR (Security Orchestration, Automation, and Response)** menutup celah *dwell time* penyerang dengan mengubah respons insiden dari hitungan jam/hari menjadi hitungan sub-detik melalui automasi API.
3. Keberhasilan automasi IR di level enterprise bertumpu pada **Safety Guardrails**: validasi *Blast Radius*, *Distributed Idempotency Locks*, *Tiered Containment*, dan sistem pengaman *Global Circuit Breakers* untuk mencegah automasi berbalik melumpuhkan infrastruktur internal.