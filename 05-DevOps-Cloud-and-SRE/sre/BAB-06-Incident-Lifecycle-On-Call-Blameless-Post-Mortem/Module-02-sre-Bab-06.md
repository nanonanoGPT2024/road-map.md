# Bab 06: Incident Lifecycle, On-Call, & Blameless Post-Mortem
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Merancang dan mengoperasikan arsitektur *Incident Command System* (ICS) adaptif untuk infrastruktur terdistribusi skala besar.
- Mengonfigurasi *alert routing engine*, *deduplication*, dan *inhibition rules* pada Prometheus Alertmanager dan Webhook Gateway enterprise guna mengeliminasi *alert fatigue*.
- Membangun otomatisasi orkestrasi insiden (*ChatOps-driven incident management*) berbasis API yang mengintegrasikan monitoring, paging, pembuatan war room, dan pencatatan audit log.
- Menganalisis insiden menggunakan metodologi *Systemic Safety Engineering* (AcciMap, STAMP/STPA) melampaui pendekatan reduksionis "Root Cause Analysis (RCA) 5-Whys".
- Mengembangkan *Action Items* berbasis *Error Budget Policy* dan merekayasa metrik keandalan MTTA, MTTD, MTTR, serta *Failure Demand vs Value Demand*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
- **Observability Primitives**: Metrik (Prometheus), Logging terpusat, dan Distributed Tracing (OpenTelemetry).
- **Service Level Engineering**: SLI, SLO, dan kalkulasi *Error Budget burn rate* (Multi-window multi-burn-rate alerts).
- **Infrastruktur & Jaringan Dasar**: HTTP/2, gRPC, webhook lifecycle, Linux system calls, DNS resolution, dan orkestrasi container (Kubernetes).
- **Dasar Pemrograman Sistem**: Menulis automasi menggunakan Python atau Go untuk integrasi REST API.

---

### 3. Concept & Internal Architecture

Manajemen insiden skala enterprise bukan sekadar merespons notifikasi; ini adalah sistem rekayasa sosio-teknis (*socio-technical systems engineering*). Arsitektur produksi penanganan insiden memisahkan jalur telemetri data (*telemetry plane*), jalur pensinyalan (*alert/signaling plane*), dan jalur koordinasi manusia (*command plane*).

```
                      +---------------------------------------+
                      |          TELEMETRY PLANE              |
                      |  Prometheus / OpenTelemetry / Logs   |
                      +-------------------+-------------------+
                                          |
                                          v Metrics / Alert Rules Firing
                      +---------------------------------------+
                      |           SIGNALING PLANE             |
                      |        Prometheus Alertmanager        |
                      |  - Deduplication & Grouping Engine    |
                      |  - Inhibition Tree Engine             |
                      |  - Routing & Escalation Matrix        |
                      +-------------------+-------------------+
                                          |
                                          | Webhook Events
                                          v
                      +---------------------------------------+
                      |         AUTOMATION GATEWAY            |
                      |      Incident Orchestration Bot       |
                      |  - PagerDuty/Opsgenie Integration     |
                      |  - Dynamic War Room Provisioning      |
                      |  - Auto-Scribe & Audit Timeline Log   |
                      +-------------------+-------------------+
                                          |
                        +-----------------+-----------------+
                        |                                   |
                        v                                   v
        +-------------------------------+   +-------------------------------+
        |         COMMAND PLANE         |   |       REMEDIATION PLANE       |
        | Incident Commander (ICS)      |   | Automated Runbooks            |
        | - Operations Lead             |   | - Self-Healing Controller     |
        | - Communications Lead         |   | - Traffic Shedding / Failover |
        | - Scribe                      |   | - Dynamic Resource Scaling    |
        +-------------------------------+   +-------------------------------+
```

#### Incident Command System (ICS) Mapping
Mengadopsi standar respon bencana FIRESCOPE yang dimodifikasi untuk software engineering:
1. **Incident Commander (IC)**: Pemilik mutlak otoritas insiden. IC tidak bertugas mendiagnosis *bug* secara langsung, melainkan mengalokasikan beban kerja, memverifikasi hipotesis, menjaga *situational awareness*, dan mengambil keputusan akhir (misal: otorisasi *failover* multi-region yang memicu *data drift*).
2. **Operations Lead (OL)**: Menjalankan eksekusi teknis dan mitigasi langsung (misal: *rollback deploy*, *traffic rerouting*, *thread dumping*). Memimpin fungsional engineer lainnya.
3. **Communications Lead (CL)**: Mengelola komunikasi eksternal dan internal stakeholder (C-levels, Support, Public Status Page) guna mencegah interupsi langsung kepada IC dan OL.
4. **Scribe**: Mendokumentasikan *timeline* kejadian, hipotesis yang diuji, tindakan yang diambil, dan output sistem secara real-time pada dokumen insiden terpusat.

#### Signaling & Alert Routing Engine
Di dalam Alertmanager, pemrosesan alert dilakukan melalui stateful pipeline:
- **Grouping**: Mengonsolidasi ratusan alert yang terpicu secara simultan dari instance mikroservis yang sama ke dalam satu notifikasi agregat (`group_by`, `group_wait`, `group_interval`).
- **Inhibition**: Aturan peredaman di mana adanya alert berprioritas tinggi (misal: `ClusterNetworkPartitionDown`) secara deterministik membungkam alert turunan (misal: ribuan `ServiceEndpointUnreachable`).
- **Silencing**: Meredam notifikasi alert berdasarkan matcher tertentu selama periode *maintenance window* atau mitigasi yang sedang berlangsung, tanpa mematikan firing status pada monitoring core.

---

### 4. Why & What

| Dimensi | Pendekatan Reaktif / Ad-Hoc | SRE Enterprise Incident Architecture |
| :--- | :--- | :--- |
| **Pola Notifikasi** | Broadcast alert ke Slack publik / SMS massal; siapapun yang bangun yang menangani. | Routing presisi berbasis *Escalation Matrix* dan jadwal On-Call, terintegrasi *dead man's switch*. |
| **Kognisi Tim** | Kognisi terfragmentasi; *Panic debug*, *alert fatigue*, *hero culture*. | Struktur ICS modular; pembagian peran kaku, mitigasi deterministik berbasis runbook. |
| **Post-Incident** | "Human error" dijadikan kesimpulan; mencari kambing hitam; revisi checklist manual. | *Blameless Post-Mortem*; analisis deviasi normal (*drift into failure*), evaluasi sistemik, rekayasa resiliensi. |
| **Metrik Kunci** | Waktu pemulihan tidak terukur atau hanya mencatat total waktu outage. | MTTA, MTTD, MTTR, MTTF, *Alert-to-Incident Ratio*, *Action Item Completion Velocity*. |

#### Metrik Kuantitatif Insiden
- **MTTD (Mean Time to Detect)**: Waktu dari anomali sistem dimulai secara aktual hingga sistem alert berubah status menjadi `FIRING`.
- **MTTA (Mean Time to Acknowledge)**: Durasi dari pengiriman halaman alert hingga primary on-call menekan tombol *Acknowledge*.
- **MTTR (Mean Time to Resolve/Mitigate)**: Durasi dari insiden diakui hingga performa sistem kembali berada di dalam batas toleransi SLO melalui tindakan mitigasi (bukan perbaikan permanen).

---

### 5. How (Workflow Detail)

```
[T0: Anomali Terjadi]
        |
        v
[SLO Error Budget Burn Rate Terlampaui]
        |
        v
[Alertmanager: Deduplication & Inhibition Engine Evaluated]
        |
        v
[Escalation Policy: On-Call Engineer Paged (PagerDuty/Webhook)]
        |
        v
[T_ack: Acknowledged by Primary On-Call]
        |
        +---> [Keputusan: Butuh Eskalasi & Struktur ICS?]
                    |
                    +--- YES ---> [Trigger Incident Declaration API]
                    |                    |
                    |                    +-> Buat War Room Slack (#inc-YYYYMMDD-slug)
                    |                    +-> Provisioning Konferensi Audio/Video
                    |                    +-> Tetapkan IC, OL, CL, Scribe
                    |                    +-> Perbarui StatusPage ke "Investigating"
                    |
                    +--- NO ----> [Lakukan Mitigasi Mandiri via Runbook]
                                         |
[Fase Mitigasi: Stabilisasi Sistem] <----+
        |
        v
[SLO Pulih, Metrik Kembali Hijau]
        |
        v
[Incident Downgrade / Resolved Ditandai di Slack Bot]
        |
        v
[Auto-Export Timeline & Logs ke Post-Mortem Workspace]
        |
        v
[Blameless Post-Mortem Review Meeting (Maksimal T+72 Jam)]
        |
        v
[JIRA Action Items Dibuat & Ditautkan ke Alokasi Error Budget]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kokpit Pesawat Komersial vs Reaksi Insiden
Ketika instrumen peringatan hidrolik menyala pada pesawat terbang komersial:
1. Kapten tidak langsung mengambil obeng dan membongkar katup di bawah lantai kabin (Anti-pattern SRE: IC langsung utak-atik SSH terminal).
2. Kapten mengasumsikan peran *Pilot Flying* atau *Pilot Monitoring*, merujuk pada *Quick Reference Handbook* (QRH / Runbook).
3. Jika masalah kritis berlanjut, kru menyatakan *Pan-Pan* atau *Mayday* (Incident Declaration), menyerahkan koordinasi lalu lintas udara kepada Air Traffic Control (Communications Lead), sementara First Officer mengeksekusi *fail-safe dump* (Mitigasi).
4. Tidak ada evaluasi penerbangan yang menyatakan "Pilot ceroboh menekan tuas"; investigasi NTSB memeriksa ergonomi tuas, kejelasan indikator visual, tingkat kelelahan shift, dan manual operasional produsen (Blameless Systemic RCA).

#### Diagram Alir Paging & Inhibisi Alertmanager

```
               [Kubernetes Node 01 Crashes (Hardware Failure)]
                                     |
               +---------------------+---------------------+
               |                                           |
               v                                           v
    [Alert: NodeNotReady]                    [Alert: PodCrashLooping x150]
    [Severity: Critical]                     [Severity: Warning]
               |                                           |
               +---------------------+---------------------+
                                     |
                                     v
                  +-------------------------------------+
                  |       ALERTMANAGER PIPELINE         |
                  |                                     |
                  | 1. Inhibition Rules Evaluator       |
                  |    - Rule: If NodeNotReady == True  |
                  |      Inhibit PodCrashLooping        |
                  |      WHERE node = alert.node        |
                  |                                     |
                  | 2. Result: PodCrashLooping SILENCED |
                  |                                     |
                  | 3. Routing Engine                   |
                  |    - Route: NodeNotReady -> SRE-Infra|
                  |    - Receiver: PagerDuty P1 Policy  |
                  +------------------+------------------+
                                     |
                                     v
                        [Trigger PagerDuty / On-Call]
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Alertmanager Inhibition & Grouping Configuration
Berikut adalah konfigurasi produksi Alertmanager (`alertmanager.yml`) yang menerapkan peredaman cascading alerts (*inhibition*) dan agregasi cerdas.

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default-webhook'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-high-priority'
      continue: true
    - match_re:
        service: ^(payment|checkout)$
      receiver: 'fintech-incident-bot'

inhibit_rules:
  # Inhibit semua service alerts jika node hosting mengalami network split / crash
  - source_match:
      alertname: 'NodeNetworkDown'
      severity: 'critical'
    target_match_re:
      alertname: '.*(Down|Slow|Unreachable)'
    equal: ['node', 'datacenter']

  # Inhibit alert warning jika alert critical yang sama sudah aktif pada service yang sama
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['service', 'instance']

receivers:
  - name: 'default-webhook'
    webhook_configs:
      - url: 'http://incident-orchestrator.monitoring.svc:8080/v1/alerts'
        send_resolved: true

  - name: 'pagerduty-high-priority'
    pagerduty_configs:
      - service_key: 'SEC_TOKEN_PAGERDUTY_PROD_TIER1'
        severity: 'critical'
        client: 'Alertmanager Enterprise'

  - name: 'fintech-incident-bot'
    webhook_configs:
      - url: 'http://incident-orchestrator.monitoring.svc:8080/v1/incidents/dispatch'
        send_resolved: true
```

#### Practical Example: Production-Grade Incident Orchestration Engine (Python/FastAPI)
Implementasi service automation webhook yang menerima alert dari Alertmanager, mengalkulasi tingkat keparahan insiden, membuat incident channel dinamis di platform koordinasi, mencatat audit log, dan mengembalikan payload penanganan:

```python
#!/usr/bin/env python3
"""
Enterprise Incident Orchestration Webhook Receiver
Engine untuk automasi declaration war room dan eskalasi berbasis payload Alertmanager.
"""

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import httpx
import logging
import os
import json
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("IncidentEngine")

app = FastAPI(title="SRE Incident Orchestration Engine", version="2.0.0")

SLACK_API_TOKEN = os.getenv("SLACK_API_TOKEN", "xoxb-mock-token")
PAGERDUTY_API_TOKEN = os.getenv("PAGERDUTY_API_TOKEN", "pd-mock-token")
SLACK_INCIDENT_PARENT_CHANNEL = "C0123456789" # #incidents-lobby

class AlertItem(BaseModel):
    status: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    startsAt: datetime
    endsAt: Optional[datetime] = None
    generatorURL: str

class AlertmanagerPayload(BaseModel):
    version: str
    groupKey: str
    status: str
    receiver: str
    groupLabels: Dict[str, str]
    commonLabels: Dict[str, str]
    commonAnnotations: Dict[str, str]
    externalURL: str
    alerts: List[AlertItem]

async def provision_incident_channel(incident_id: str, service: str, severity: str) -> str:
    """Membuat Slack channel baru untuk war room insiden secara dinamis."""
    channel_name = f"inc-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{service}-{incident_id[-4:]}".lower()
    headers = {"Authorization": f"Bearer {SLACK_API_TOKEN}", "Content-Type": "application/json"}
    
    async with httpx.AsyncClient() as client:
        # Mocking API Call ke Slack SDK/REST API
        logger.info(f"Mengalokasikan dedicated war room channel: #{channel_name}")
        payload = {"name": channel_name, "is_private": False}
        # resp = await client.post("https://slack.com/api/conversations.create", headers=headers, json=payload)
        # response_data = resp.json()
        channel_id = f"C_DUMMY_{incident_id[-4:]}"
        
        # Kirimkan instruksi ICS awal ke dalam channel baru
        initial_broadcast = {
            "channel": channel_id,
            "text": (
                f":fire: *INCIDENT DECLARED: {service} ({severity.upper()})*\n"
                f"*Incident ID:* `{incident_id}`\n"
                f"*Aturan Permainan ICS:*\n"
                f"- Tunjuk *Incident Commander* dengan command: `/ic claim`\n"
                f"- Rekam tindakan dengan: `/scribe note <aksi>`\n"
                f"- Tautan Bridge Audio: https://meet.company.internal/warroom-{incident_id}\n"
                f"- Runbook Repository: https://runbooks.company.internal/{service}"
            )
        }
        logger.info(f"Mengirimkan ICS Operational Directive ke {channel_id}")
        return channel_id

async def record_incident_audit_log(incident_id: str, payload: AlertmanagerPayload):
    """Mencatat artefak log untuk keperluan data forensic dan post-mortem."""
    audit_record = {
        "incident_id": incident_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": payload.status,
        "common_labels": payload.commonLabels,
        "alert_count": len(payload.alerts),
        "firing_alerts": [
            {
                "alertname": a.labels.get("alertname"),
                "startsAt": a.startsAt.isoformat(),
                "summary": a.annotations.get("summary", "N/A")
            }
            for a in payload.alerts
        ]
    }
    # Menulis append-only audit trace ke disk/object-store
    with open(f"/tmp/audit_{incident_id}.json", "w") as f:
        json.dump(audit_record, f, indent=2)
    logger.info(f"Audit log insiden {incident_id} berhasil dipersistensikan.")

async def process_orchestration(payload: AlertmanagerPayload):
    if payload.status != "firing":
        logger.info("Alert payload berstatus RESOLVED. Melewati siklus eskalasi baru.")
        return

    service = payload.commonLabels.get("service", "unknown-service")
    severity = payload.commonLabels.get("severity", "warning")
    incident_id = f"INC-{int(datetime.now(timezone.utc).timestamp())}"

    # Hanya picu pembuatan ICS Channel untuk level critical
    if severity == "critical":
        channel_id = await provision_incident_channel(incident_id, service, severity)
        await record_incident_audit_log(incident_id, payload)
        logger.info(f"Orkestrasi P1/Critical selesai. Incident {incident_id} aktif di channel {channel_id}")
    else:
        logger.info(f"Insiden non-critical ({severity}) diproses via alur reguler.")

@app.post("/v1/incidents/dispatch", status_code=202)
async def handle_alertmanager_webhook(payload: AlertmanagerPayload, background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(process_orchestration, payload)
        return {"status": "accepted", "message": "Incident payload enqueued for orchestration"}
    except Exception as e:
        logger.error(f"Gagal memproses Alertmanager webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal orchestration dispatch failure")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

---

### 8. Real World Case Study: E-Commerce Payment Gateway Cascading Blackout

#### Konteks
Sebuah platform e-commerce memproses 45.000 transaksi pembayaran per detik (TPS) selama ajang Flash Sale 11.11. 

#### Trigger Insiden
Sebuah migrasi database minor menyebabkan indeks pada tabel transaksi sekunder hilang (`idx_order_lookup_status`). Hal ini memicu *Full Table Scan* pada cluster PostgreSQL Aurora master.

#### Rantai Kegagalan Eskalasi
1. Query latensi melonjak dari 15ms menjadi 12.000ms.
2. Connection pool (`HikariCP`) pada 120 pods *Payment Processing Service* terkuras (*starvation*).
3. Pod liveness probe berbasis HTTP timeout, menyebabkan kubelet secara simultan me-restart seluruh 120 pods.
4. Terjadi *Thundering Herd Problem*: 120 pods secara bersamaan mencoba *cold boot*, menghubungkan diri ke DB yang sedang kritis, memicu kegagalan total database authentication handshake.
5. Terjadi *Alert Storm*: 14.500 alert individual terpicu dalam tempo 3 menit ke PagerDuty. Primary on-call mengalami *cognitive overload*.

#### Intervensi Incident Command System
1. **Penerapan ICS**: Principal SRE mengaktifkan command bridge, mengambil alih kendali sebagai Incident Commander (IC). IC membagi tugas secara tegas:
   - *Operations Lead 1*: Mematikan traffic sementara (*hard shedding*) pada Ingress Gateway menggunakan Cloudflare Rate Limiting Worker untuk memberi ruang bernapas pada database.
   - *Operations Lead 2*: Menaikkan connection limit PostgreSQL dan menambahkan indeks secara offline di read-replica staging untuk menghitung waktu build index.
   - *Communications Lead*: Mengirimkan notifikasi berkala setiap 15 menit ke merchant partner dan C-levels melalui internal dashboard status page.
2. **Mitigasi**:
   - Mematikan dependency liveness probe yang merestart pod saat koneksi DB lambat (mengubahnya menjadi graceful degradation: return HTTP 429 ke payment partner daripada crashing).
   - Ingress memvalidasi queue transaksi melalui Redis buffer terdistribusi, mengurangi pressure langsung ke DB hingga indeks selesai dibuat menggunakan `CREATE INDEX CONCURRENTLY`.
3. **Hasil Metrik**:
   - *MTTD*: 1 menit 12 detik.
   - *MTTA*: 45 detik.
   - *MTTR*: 42 menit (Mitigasi traffic shedding aktif di menit ke-14, menstabilkan cluster).

---

### 9. Trade-offs

```
                       [AGRESSIVE AUTOMATION]
                       /                    \
                      /                      \
                     /                        \
    (Risk of Split-Brain /               (Faster MTTR /
     Destructive Actions)                Lower Human Fatigue)
                   /                            \
                  /                              \
[MANUAL HUMAN-IN-THE-LOOP] ------------------ [OVER-ENGINEERED ESCALATION]
(High MTTR / Human Cognitive Burnout)        (High Tooling Maintenance Cost /
                                              Configuration Drift)
```

| Parameter | Pendekatan Terlalu Agresif | Pendekatan Terlalu Manual / Terkonservasi | Titik Optimal SRE Enterprise |
| :--- | :--- | :--- | :--- |
| **Alert Sensitivity** | Alert terpicu pada ambang batas statis 80% CPU; alert storming. | Alert hanya terpicu saat seluruh cluster down. | Multi-window Multi-burn-rate berbasis SLO Error Budget. |
| **Self-Healing Runbooks** | Skrip otomatis melakukan restart database dan flush cache seketika. | Setiap tindakan command mitigasi membutuhkan persetujuan tiket Change Request (CAB). | Automasi non-destruktif (*cordon node*, *traffic shedding*); otorisasi manual untuk tindakan destruktif. |
| **Post-Mortem Policy** | Menuntut penyelesaian post-mortem untuk setiap issue minor (P3/P4). | Post-mortem hanya dibuat saat ada keluhan direksi (High Visibility). | Mandatory Post-Mortem untuk setiap insiden P1/P2 atau insiden dengan *Near-Miss* signifikan. |
| **On-Call Rotation Size** | 2-3 orang engineers (risiko kelelahan, *single point of knowledge*). | 20+ orang tidak terspesialisasi (kehilangan refleks operasional, *bystander effect*). | 6-8 engineers per rotation; primer dan sekunder; rotasi shift mingguan terstruktur. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Anti-Pattern: "Human Error" Sebagai Akar Masalah
- **Kesalahan**: Menuliskan kesimpulan post-mortem seperti: *"Penyebab insiden adalah engineer A salah mengeksekusi DROP TABLE di production."*
- **Koreksi Arsitektural**: Manusia tidak pernah menjadi akar masalah; manusia adalah garis pertahanan terakhir dari sistem yang rapuh. Investigasi mengapa engineer memiliki akses langsung DROP TABLE di terminal prod? Mengapa tooling database tidak memblokir operasi DDL non-whitelisted? Mengapa skema verifikasi peer-review tidak menangkapnya?

#### 2. Alert Fatigue Akibat Flapping Alerts
- **Gejala**: On-call engineer terbangun 5 kali dalam semalam oleh alert yang firing selama 15 detik lalu resolve secara otomatis.
- **Troubleshooting & Remediasi**:
  Terapkan parameter `for` di Prometheus Alerting rules dan gunakan fungsi `deriv()` atau `predict_linear()` alih-alih data mentah instan:
  ```yaml
  # BURUK: Sangat sensitif terhadap spike sementara
  - alert: MemoryUsageHigh
    expr: process_resident_memory_bytes / memory_limit > 0.9

  # BAIK: Memerlukan kondisi konstan sebelum memicu sinyal
  - alert: MemoryUsageHigh
    expr: process_resident_memory_bytes / memory_limit > 0.9
    for: 10m
  ```

#### 3. Incident Commander Ikut Melakukan Debugging Teknis
- **Gejala**: War room hening selama 30 menit karena IC sibuk melihat terminal Grafana dan mencari query SQL sendiri.
- **Troubleshooting**: Jika IC terjerumus dalam investigasi teknis, segera delegasikan peran IC ke orang lain (misal: Scribe naik menjadi IC, atau OL mengambil peran koordinasi). IC harus mempertahankan pandangan makro helikopter (*helicopter view*).

---

### 11. Best Practices (Production Checklist)

#### Pre-Incident Readiness
- [ ] Jadwal on-call diverifikasi di PagerDuty/Opsgenie minimal 2 minggu di muka dengan secondary layer aktif.
- [ ] Skema "Dead Man's Snitch" terpasang untuk memonitor apakah Alertmanager itu sendiri masih hidup dan mengirim sinyal *heartbeat*.
- [ ] Runbook link wajib tercantum di setiap anotasi `runbook_url` pada rules Prometheus.
- [ ] Akses break-glass / privileged identity management (PIM) telah divalidasi dan diuji setiap kuartal.

#### During-Incident Command
- [ ] IC mengambil komando tegas: *"Saya mengambil peran Incident Commander. Tolong update temuan hanya lewat channel ini."*
- [ ] War room Slack terisolasi dibuat secara terotomatisasi; hindari koordinasi di channel general.
- [ ] Mengalokasikan 1 orang Scribe untuk mencatat setiap timestamp kejadian penting.
- [ ] Terapkan timebox (maksimal 15-20 menit) untuk setiap pengujian hipotesis mitigasi sebelum berpindah ke rencana cadangan.

#### Post-Incident Governance
- [ ] War room timeline diekspor dalam 24 jam pertama pasca insiden.
- [ ] Draft Blameless Post-Mortem selesai maksimal T+48 jam.
- [ ] Review meeting post-mortem dihadiri lintas divisi (Dev, SRE, Product, QA).
- [ ] Seluruh Action Items memiliki format SMART (*Specific, Measurable, Achievable, Relevant, Time-bound*) dan ditautkan ke backlog Sprint dengan prioritas setara bug P0/P1.

---

### 12. Hands-on Practice

Buat seluruh file praktikum di direktori: `hands-on/m02/`

#### Struktur Direktori:
```
hands-on/m02/
├── alertmanager/
│   └── alertmanager.yml
├── prometheus/
│   ├── alert.rules.yml
│   └── prometheus.yml
├── orchestrator/
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
└── docker-compose.yml
```

#### Langkah 1: Buat Direktori Proyek
```bash
mkdir -p hands-on/m02/{alertmanager,prometheus,orchestrator}
cd hands-on/m02
```

#### Langkah 2: Setup Alertmanager Config (`alertmanager/alertmanager.yml`)
```yaml
global:
  resolve_timeout: 1m

route:
  group_by: ['alertname', 'service']
  group_wait: 5s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'incident-orchestrator-gateway'

receivers:
  - name: 'incident-orchestrator-gateway'
    webhook_configs:
      - url: 'http://orchestrator:8080/v1/incidents/dispatch'
        send_resolved: true
```

#### Langkah 3: Setup Prometheus Alerts (`prometheus/alert.rules.yml`)
```yaml
groups:
  - name: CorePlatformAlerts
    rules:
      - alert: ServiceLatencyHigh
        expr: http_request_duration_seconds{quantile="0.99"} > 2.0
        for: 5s
        labels:
          severity: critical
          service: payment-gateway
        annotations:
          summary: "Payment Gateway latency critical spike"
          description: "Latency p99 melampaui 2 detik selama lebih dari 5 detik."
          runbook_url: "https://wiki.internal/runbooks/payment-latency"
```

#### Langkah 4: Setup Prometheus Config (`prometheus/prometheus.yml`)
```yaml
global:
  scrape_interval: 2s
  evaluation_interval: 2s

rule_files:
  - "/etc/prometheus/alert.rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  - job_name: 'mock-target'
    static_configs:
      - targets: ['orchestrator:8080']
```

#### Langkah 5: Implementasi Orchestrator & Mock Metric Exporter (`orchestrator/app.py`)
```python
from fastapi import FastAPI, BackgroundTasks, Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from prometheus_client import make_asgi_app, Summary
import logging
import json
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LabOrchestrator")

app = FastAPI(title="Lab Incident Orchestrator")

# Expose Prometheus metric endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

LATENCY_METRIC = Summary("http_request_duration_seconds", "HTTP Request Duration", ["quantile"])

# Simulated state
simulate_degradation = False

@app.get("/simulate/inject-failure")
def inject_failure():
    global simulate_degradation
    simulate_degradation = True
    logger.warning("Kegagalan disimulasikan: Latensi P99 sekarang diset > 2.5s!")
    return {"status": "Failure injected: Latency critical threshold breached"}

@app.get("/simulate/recover")
def recover():
    global simulate_degradation
    simulate_degradation = False
    logger.info("Pemulihan disimulasikan: Latensi kembali normal.")
    return {"status": "Recovery executed"}

@app.get("/api/v1/checkout")
def checkout_endpoint():
    global simulate_degradation
    if simulate_degradation:
        # Simulasi latensi rusak
        LATENCY_METRIC.labels(quantile="0.99").observe(2.8)
        time.sleep(0.1)
        return {"status": "slow", "latency": "2.8s"}
    else:
        LATENCY_METRIC.labels(quantile="0.99").observe(0.05)
        return {"status": "healthy", "latency": "0.05s"}

@app.post("/v1/incidents/dispatch")
async def dispatch_webhook(payload: Dict[str, Any]):
    logger.info("=== NOTIFIKASI WEBHOOK DITERIMA DARI ALERTMANAGER ===")
    logger.info(json.dumps(payload, indent=2))
    
    status = payload.get("status")
    alerts = payload.get("alerts", [])
    
    if status == "firing":
        for alert in alerts:
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            logger.info(f"🔥 [AUTO-INCIDENT] Mengeskalasi insiden untuk service: {labels.get('service')}")
            logger.info(f"📢 [WAR-ROOM] Berhasil membuat #inc-warroom-{labels.get('service')}")
            logger.info(f"📖 [RUNBOOK] {annotations.get('runbook_url')}")
    elif status == "resolved":
        logger.info("✅ [AUTO-RESOLVE] Sistem kembali stabil. Menutup sesi war room & menjadwalkan post-mortem.")
        
    return {"status": "processed"}
```

#### Langkah 6: Requirements & Dockerfile (`orchestrator/`)
`orchestrator/requirements.txt`:
```txt
fastapi>=0.100.0
uvicorn>=0.22.0
prometheus-client>=0.17.0
httpx>=0.24.0
pydantic>=2.0.0
```

`orchestrator/Dockerfile`:
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

#### Langkah 7: Deklarasikan Lingkungan Produksi Lokal (`docker-compose.yml`)
```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:v2.45.0
    container_name: lab-prometheus
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alert.rules.yml:/etc/prometheus/alert.rules.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.enable-lifecycle'
    ports:
      - "9090:9090"
    depends_on:
      - alertmanager

  alertmanager:
    image: prom/alertmanager:v0.25.0
    container_name: lab-alertmanager
    volumes:
      - ./alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
    ports:
      - "9093:9093"

  orchestrator:
    build:
      context: ./orchestrator
    container_name: lab-orchestrator
    ports:
      - "8080:8080"
```

#### Langkah 8: Verifikasi & Uji Skenario Insiden
1. Jalankan cluster observabilitas:
   ```bash
   docker compose up --build -d
   ```
2. Pastikan target terhubung di Prometheus: Buka `http://localhost:9090/targets`
3. Ambil metrik awal agar Prometheus mulai mengindeks:
   ```bash
   curl http://localhost:8080/api/v1/checkout
   ```
4. **Picukan Insiden (Injeksi Latensi Buruk)**:
   ```bash
   curl http://localhost:8080/simulate/inject-failure
   # Picu evaluasi endpoint berkala
   for i in {1..10}; do curl -s http://localhost:8080/api/v1/checkout; sleep 1; done
   ```
5. Pantau logs pada Incident Orchestrator:
   ```bash
   docker compose logs -f orchestrator
   ```
   *Amati keluaran log saat alert bertransisi dari firing ke pembuatan war room otomatis.*
6. **Pulihkan Sistem**:
   ```bash
   curl http://localhost:8080/simulate/recover
   for i in {1..5}; do curl -s http://localhost:8080/api/v1/checkout; sleep 1; done
   ```
   *Amati Webhook menerima notifikasi state RESOLVED.*

---

### 13. Exercise

#### Level Easy
Konfigurasikan sebuah rule Alertmanager baru pada file `alertmanager/alertmanager.yml` yang mengarahkan semua alert dengan label `environment: staging` ke `receiver: 'blackhole'` (dibuang tanpa routing webhook).
- **Kriteria Keberhasilan**: Alert dengan label `staging` tidak pernah memicu webhook log di service orchestrator, sementara alert `production` tetap terkirim normal.

#### Level Medium
Perluas service Python `orchestrator/app.py` agar mengimplementasikan *deduplication cache* berbasis sliding window in-memory (atau Redis dict). Jika terdapat 5 webhook dengan `alertname` yang sama dalam kurun waktu kurang dari 60 detik, hanya eksekusi pembukaan war room 1 kali dan catat peringatan *"Suppressed duplicate alert notification"* untuk sisanya.
- **Kriteria Keberhasilan**: Mengirim 10 webhook serentak hanya menghasilkan tepat 1 pesan pembukaan war room di log.

#### Level Hard
Rancang dan implementasikan endpoint `/v1/postmortem/generate` pada `orchestrator/app.py`. Endpoint ini harus menerima `incident_id`, lalu membaca log rekaman insiden lokal, mengambil statistik durasi total (`endsAt - startsAt`), dan menghasilkan output dokumen Markdown terstruktur berstandar industri lengkap dengan:
1. Executive Summary
2. Impacted SLIs & Error Budget Burned
3. Chronological Timeline (UTC)
4. Triggering Conditions
5. Failure Domain Analysis
- **Kriteria Keberhasilan**: Skrip menghasilkan file Markdown yang valid secara sintaksis dan bebas dari bahasa atribusi kesalahan individu (*blameless phrasing*).

---

### 14. Challenge

#### Skenario: Arsitektur Cross-Region Dual-Control Cascading Failover Guard

#### Deskripsi Tantangan
Perusahaan finansial Anda beroperasi di dua region AWS: `ap-southeast-1` (Primary) dan `ap-southeast-3` (Secondary). Database direplikasi secara asynchronous. 
Terdapat kebutuhan implementasi *Automated Disaster Recovery Orchestration*:
1. Jika availability SLI di Primary jatuh di bawah 95% selama 3 menit, sistem alert harus memicu automated workflow failover.
2. Namun, ada bahaya nyata: Terjadinya *false positive network partition* (Split-Brain scenario) yang dapat memicu failover saat database primary sebenarnya masih menerima transaksi, yang akan berakibat fatal pada integritas data uang (*ledger inconsistency*).
3. Anda diminta merancang arsitektur controller mitigasi insiden yang:
   - Menggunakan mekanisme *Consensus Quorum Check* minimal dari 3 titik observasi independen (Worker Region 1, Worker Region 2, dan External Cloud Provider / Cloudflare Worker) sebelum memvalidasi bahwa Primary benar-benar down secara objektif.
   - Mengintegrasikan gerbang *Human-in-the-Loop Verification*: Orkestrator mengirimkan push challenge interaktif dengan timebox 90 detik ke Incident Commander (via Slack Block Kit dengan Signed JWT verification).
   - Jika IC menekan "Authorize Failover" atau timeout 90 detik tercapai dengan parameter Quorum = 3/3 DOWN, orkestrator mengeksekusi fencing (*stonith/demote primary*), melepaskan status read-only secondary, dan mengubah entri DNS Route53/Cloudflare via API.

#### Deliverable Arsitektur
1. Diagram urutan (Sequence Diagram ASCII/PlantUML) alur verifikasi multi-voter dan eksekusi mitigasi.
2. Spesifikasi penanganan kegagalan (*Failure Mode and Effects Analysis* - FMEA) jika controller failover itu sendiri terputus jaringan di tengah proses failover.
3. Skema *Rollback Matrix* jika failover regional gagal diselesaikan dalam 5 menit.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda & Konseptual Singkat)

**Q1: Apa peran utama seorang Incident Commander (IC) selama penanganan insiden skala P1/Critical?**
- A. Menulis kode perbaikan hotfix dan mendistribusikannya langsung ke server produksi.
- B. Memegang otoritas penuh terhadap koordinasi, strategi alokasi peran, dan pengambilan keputusan tingkat tinggi tanpa terlibat dalam pekerjaan implementasi teknis mikro.
- C. Berbicara langsung dengan media massa dan regulator perbankan.
- D. Memeriksa baris per baris audit log untuk menemukan siapa engineer yang bersalah.
*Jawaban: B. IC berfokus pada koordinasi tingkat makro, delegasi, dan penjagaan objektivitas strategi mitigasi.*

**Q2: Mengapa konsep "Root Cause" tunggal dianggap cacat (*flawed*) dalam analisis rekayasa sistem terdistribusi modern?**
- A. Karena sistem modern tidak memiliki dependensi yang kompleks.
- B. Karena kegagalan sistem sosio-teknis selalu berakar dari konvergensi multi-faktor yang saling berkelindan (*contributing factors*), bukan satu titik kesalahan terisolasi.
- C. Karena database modern tidak dapat mengalami crash.
- D. Hanya untuk melindungi engineer agar tidak dipecat oleh manajemen.
*Jawaban: B. Dalam sistem terdistribusi kompleks, kegagalan timbul dari kombinasi kondisi tak terduga (*latent conditions*) dan kegagalan komponen jamak yang berinteraksi.*

**Q3: Pada Alertmanager, fitur apa yang secara deterministik membungkam alert dependensi tingkat rendah ketika alert infrastruktur tingkat tinggi sedang firing?**
- A. Grouping
- B. Silencing
- C. Inhibition
- D. Throttling
*Jawaban: C. Inhibition rules mematikan alert tertentu jika alert target lain yang cocok sedang aktif.*

**Q4: Apa perbedaan esensial antara MTTR (Mean Time to Resolve) dan MTTM (Mean Time to Mitigate)?**
- A. MTTR mengukur perbaikan permanen kode (termasuk post-mortem), sedangkan MTTM mengukur waktu hingga dampak buruk terhadap customer berhasil dihentikan (workaround/traffic shed).
- B. Keduanya adalah istilah identik tanpa perbedaan teknis.
- C. MTTM selalu lebih lama daripada MTTR.
- D. MTTR hanya digunakan untuk hardware, MTTM untuk software.
*Jawaban: A. SRE memprioritaskan MTTM (mengembalikan kepuasan user/SLO terlebih dahulu) sebelum menyelesaikan MTTR struktural.*

**Q5: Apakah metrik CPU Utilization 95% secara independen valid dijadikan alert dengan prioritas P1 (Pager Waking Alert)?**
- A. Ya, karena CPU tinggi pasti merusak server.
- B. Tidak. SRE berorientasi pada user-facing symptoms (SLI/SLO) seperti latency atau error rate. CPU 95% adalah indikator kapasitas internal yang bisa jadi merupakan operasi normal batch worker.
- C. Ya, jika server tersebut menggunakan Linux kernel lama.
- D. Tergantung pada vendor cloud yang digunakan.
*Jawaban: B. Alerting paging harus berorientasi pada gejala langsung kegagalan layanan yang dirasakan pengguna atau ancaman langsung terhadap Error Budget.*

---

#### Bagian 2: Intermediate (Analisis Penerapan)

**Q6: Alertmanager Anda mengirimkan notifikasi 200 pod down secara individual ke handphone on-call engineer dalam waktu 30 detik. Parameter konfigurasi apa yang salah dikonfigurasi?**
- A. Nilai `repeat_interval` terlalu tinggi.
- B. Ketiadaan konfigurasi `group_by` yang menyatukan alert berdasarkan `cluster` atau `service`, dan nilai `group_wait` yang disetel ke 0.
- C. DNS Prometheus server mati.
- D. Webhook server menggunakan HTTP/1.1 bukan HTTP/2.
*Jawaban: B. `group_by` mengelompokkan alert serupa, dan `group_wait` memberikan jendela waktu penundaan bagi Alertmanager untuk mengumpulkan alert lain sebelum mengirimkan notifikasi batch tunggal.*

**Q7: Mengapa post-mortem harus bersifat Blameless (Tanpa Menyalahkan)? Berikan alasan dari sudut pandang rekayasa reliabilitas sistem.**
- A. Agar suasana kerja santai dan developer tidak perlu merasa bertanggung jawab atas kinerjanya.
- B. Jika kegagalan dihukum, engineer akan menyembunyikan detail insiden, menutupi kesalahan, dan memalsukan timeline. Akibatnya, akar kerentanan sistemik tidak akan pernah teridentifikasi dan sistem tetap rentan meledak di masa depan.
- C. Karena kesalahan manusia selalu diakibatkan oleh bug vendor pihak ketiga.
- D. Blameless post-mortem adalah aturan hukum perdata di bidang komputasi awan internasional.
*Jawaban: B. Blameless culture adalah strategi keselamatan sistem untuk menjamin transparansi data investigasi secara objektif tanpa ketakutan defensif dari operator.*

**Q8: Anda memiliki burn rate sebesar 14.4x dari total Error Budget 30 hari. Berapa persen Error Budget yang akan habis terbakar jika kondisi ini dibiarkan selama 1 jam?**
- A. 1%
- B. 2%
- C. 5%
- D. 14.4%
*Perhitungan:*
- 1 bulan = 720 jam.
- Pada burn rate 1x, 100% budget habis dalam 720 jam (1 jam = 1/720 = 0.1388%).
- Pada burn rate 14.4x: 14.4 * (1 / 720) = 14.4 / 720 = 0.02 (yakni 2%).
*Jawaban: B. 2% dari total error budget 30 hari lenyap dalam tempo 1 jam.*

**Q9: Apa tujuan utama menyertakan tautan Runbook eksplisit di setiap notifikasi alert Prometheus?**
- A. Memenuhi dokumentasi ISO-27001 saja.
- B. Mengurangi *cognitive load* on-call engineer saat terbangun pada jam 3 pagi dengan instruksi mitigasi yang terverifikasi dan presisi, sehingga memangkas MTTR.
- C. Menghindari kebutuhan pelatihan bagi engineer baru.
- D. Membatasi tanggung jawab pembuat alert jika terjadi insiden.
*Jawaban: B. Mengurangi kebingungan saat stres tinggi dan mempercepat diagnosa dengan langkah langkah operasional yang deterministik.*

**Q10: Dalam insiden kritis, Communications Lead (CL) merilis status ke pihak publik: "Layanan kami diretas dan seluruh data hilang," padahal investigasi teknis baru menemukan adanya network partition pada etcd cluster. Prinsip komunikasi krisis apa yang dilanggar?**
- A. Menolak berkomunikasi dengan pihak luar.
- B. Spekulasi prematur tanpa konfirmasi teknis dari Incident Commander. Komunikasi krisis wajib faktual, terverifikasi, ringkas, dan selaras dengan realitas teknis terkini.
- C. Terlalu lambat merilis status.
- D. Menggunakan bahasa Indonesia yang kurang santun.
*Jawaban: B. Spekulasi destruktif merusak reputasi dan memicu kepanikan yang tidak didasarkan pada fakta telemetri sistem.*

---

#### Bagian 3: Evaluasi Kasus Produksi Nyata

**Skenario Kasus 1: "The Flapping Alert Storm"**
Tim SRE Anda mendeteksi bahwa setiap hari Minggu pukul 02:00 UTC, terjadi 40 alert paging yang menyala dan mati kembali (*flapping*) selama durasi 10 menit, tepat ketika cron job pembersihan data rutin dijalankan. On-call engineer selalu terbangun namun tidak mengambil tindakan karena sistem pulih sendiri dalam 15 menit. Analisis kegagalan arsitektur apa yang terjadi dan bagaimana solusinya?
- **Solusi**:
  1. *Masalah*: Alerting rules mengevaluasi metrik sekunder secara instan tanpa memperhitungkan periode pemeliharaan terencana (*maintenance window*) atau jendela durasi (`for: 15m`).
  2. *Solusi*: Terapkan *Silence API call* otomatis via cron job sebelum job pembersihan jalan dan hapus silence saat selesai, ATAU sesuaikan alerting rule agar mengabaikan transient spike dengan memantau dampak langsung pada latensi end-user (SLO), bukan sekadar memory/disk I/O utilitas cron worker.

**Skenario Kasus 2: "The Cascade of Authorization"**
Saat terjadi insiden P1 di mana service Auth down total, engineer mencoba mengakses Kubernetes production via `kubectl`. Namun, cluster Kubernetes dikonfigurasi untuk memvalidasi user token via OIDC yang menunjuk ke service Auth yang sedang down tersebut. Seluruh tim terkunci dari cluster (*Deadlock/Circular Dependency*). 
Identifikasi perbaikan struktural yang wajib dimasukkan ke dalam Action Items Post-Mortem!
- **Solusi**:
  1. Identifikasi *Circular Dependency*: Keandalan sistem autentikasi darurat bergantung pada ketersediaan sistem yang diaturnya sendiri.
  2. *Action Item Struktural*: Implementasikan mekanisme *Break-Glass Emergency Access* berbasis X.509 client certificate statis yang ditandatangani oleh root internal cluster CA, disimpan pada encrypted offline vault (misal: HashiCorp Vault offline token atau hardware token terisolasi), yang tidak bergantung pada OIDC identity provider eksternal.

**Skenario Kasus 3: "The Action Item Bankruptcy"**
Sebuah divisi engineering memiliki 87 daftar *Action Items* dari post-mortem insiden masa lalu yang tidak pernah disentuh selama 6 bulan karena tim produk memprioritaskan fitur baru. Pada bulan ke-7, insiden dengan karakteristik yang identik terulang kembali dan merugikan perusahaan sebesar $500,000. Kebijakan tata kelola SRE apa yang gagal diterapkan?
- **Solusi**:
  1. *Kegagalan Tata Kelola*: Ketiadaan implementasi *Error Budget Policy* yang mengikat secara organisasional.
  2. *Remediasi*: Terapkan aturan tata kelola tegas: Jika Error Budget habis atau jika terdapat Post-Mortem Action Item level P0/P1 yang melewati batas SLA (misal: > 30 hari belum selesai), *Feature Freeze* otomatis berlaku. Seluruh kapasitas sprint engineering dialihkan 100% untuk menyelesaikan hutang keandalan (*reliability debt*) tersebut sebelum fitur bisnis baru diizinkan meluncur ke tahap rilis.

---

### 16. Summary

```
                      +---------------------------------------+
                      |       THE INCIDENT VALUE LOOP         |
                      +---------------------------------------+
                                          |
                                          v
                              [ DETECT & ESCALATE ]
                              - High-fidelity SLI Alerts
                              - Deduplicated / Inhibited Paging
                                          |
                                          v
                              [ COMMAND & MITIGATE ]
                              - ICS Role Distribution
                              - Runbook Execution / Traffic Shed
                              - Protect Error Budget
                                          |
                                          v
                              [ LEARN & EVOLVE ]
                              - Blameless Post-Mortem
                              - AcciMap / Latent Factor Tracking
                              - Mandatory Reliability SLA Tickets
                                          |
                                          +--- (Feeds back into System Hardening)
```

1. **Insiden Adalah Sumber Informasi Paling Berharga**: Sistem terdistribusi yang tidak pernah mengalami insiden adalah ilusi atau sistem yang belum diuji pada skala sebenarnya. Penanganan insiden enterprise bukan tentang menghukum orang yang melakukan kesalahan pengetikan, melainkan memperkuat pertahanan arsitektural di sekitar sistem.
2. **Kekakuan ICS vs Fleksibilitas Rekayasa**: Dengan membagi peran antara Incident Commander (IC), Operations Lead (OL), Communications Lead (CL), dan Scribe, kita menghilangkan kebingungan operasional saat stres tinggi dan memastikan mitigasi berlangsung deterministik.
3. **Penyaringan Sinyal di Jalur Signaling**: Alertmanager bertindak sebagai benteng yang menyaring derau (*noise*). Tanpa deduplikasi, grouping, dan inhibisi, on-call engineer akan mengalami kelelahan kognitif (*alert fatigue*) yang menjamin terjadinya kelalaian manusia saat krisis besar datang.
4. **Post-Mortem Adalah Rekayasa, Bukan Birokrasi**: Mengubah insiden menjadi dokumen post-mortem tanpa menyalahkan siapapun (*blameless*) bukan semata-mata etika sosial, melainkan prasyarat mutlak untuk mendapatkan data empiris yang akurat demi menjamin resiliensi sistem di masa depan.