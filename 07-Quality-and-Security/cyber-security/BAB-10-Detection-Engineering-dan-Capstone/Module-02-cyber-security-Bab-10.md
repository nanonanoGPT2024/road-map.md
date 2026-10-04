# BAB 10: Detection Engineering dan Capstone
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta mampu:
1. **Merancang dan Mengoperasikan Pipeline Detection-as-Code (DaC)**: Mengotomatisasi siklus hidup aturan deteksi (authoring, testing, validation, deployment) menggunakan Git, CI/CD, dan format agnostik seperti Sigma.
2. **Membangun Arsitektur Streaming Detection Skala Enterprise**: Menerapkan pemrosesan event terdistribusi (Distributed Event Streaming) untuk korelasi log berkecepatan tinggi (*high EPS/Events Per Second*) dengan latensi sub-detik.
3. **Mengimplementasikan Continuous Detection Validation**: Memvalidasi ketahanan deteksi terhadap teknik TTP MITRE ATT&CK menggunakan automated adversary emulation framework (seperti Atomic Red Team) di lingkungan staging/canary.
4. **Mengoptimalkan Signal-to-Noise Ratio (SNR)**: Mereduksi false positive secara terukur melalui algoritma *context enrichment*, stateful tracking, dan dynamic baselining.
5. **Mengintegrasikan Detection Pipeline dengan SOAR**: Mengotomatisasi triage, deduplikasi, dan penambahan konteks forensik sebelum alert dialirkan ke Security Operations Center (SOC).

---

### 2. Prerequisite

Peserta wajib menguasai:
- **Foundational Detection Engineering**: Pemahaman mendalam tentang Piramida Rasa Sakit (*Pyramid of Pain* David Bianco), MITRE ATT&CK Framework, dan taksonomi log sistem (Sysmon, Windows Event Log, Linux Auditd, CloudTrail).
- **Format Spesifikasi Deteksi**: Sintaks dasar Sigma Rule, YARA-L, atau SPL (Splunk Processing Language) / KQL (Kusto Query Language).
- **Pemrograman & Skrip**: Python 3.11+ (asyncio, data parsing, HTTP client, pySigma) dan Bash/PowerShell scripting.
- **Infrastruktur & Orkestrasi**: Dasar-dasar Apache Kafka/Redpanda, Docker, Kubernetes, dan sistem CI/CD (GitHub Actions atau GitLab CI).
- **Dasar Jaringan & Sistem**: Mekanisme RPC/WMI, Kerberos, SAML, DNS tunneling, dan eksekusi sub-proses sistem operasi.

---

### 3. Concept & Internal Architecture (Mendalam)

#### Arsitektur Modern Detection Engineering Pipeline (DaC Engine)
Arsitektur deteksi modern menggeser paradigma dari konfigurasi manual GUI pada SIEM menjadi pendekatan berbasis perangkat lunak:

```
[Developer / Engineer]
        │  (Git Push: Sigma / Detection Rule)
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. CI/CD Validation & Build Pipeline                        │
│   ├── Linting & Syntax Validation (yamllint, custom schema)  │
│   ├── Mapping Validation (MITRE ATT&CK ID, Data Model)      │
│   ├── Transpilation via pySigma (Sigma -> SIEM/EDR Target)  │
│   └── Automated Adversary Emulation (Atomic Red Team Run)    │
└─────────────────────────────────────────────────────────────┘
        │  (Deploy Artifacts via API)
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Real-Time Ingestion & Streaming Correlation Engine       │
│   ├── Log Producers (Sysmon, CrowdStrike, Auditd, K8s)      │
│   ├── Message Broker (Apache Kafka / Distributed Log Bus)   │
│   ├── Stream Processing (Apache Flink / Vector Engine)      │
│   └── Stateful Complex Event Processing (CEP) Context Cache │
└─────────────────────────────────────────────────────────────┘
        │  (Matches / Alerts Triggered)
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Automated Enrichment & Alert Triage Layer                │
│   ├── Asset DB / Identity Context Injection (LDAP/CMDB)     │
│   ├── Threat Intelligence Feed Correlation (MISP/Redis)     │
│   ├── Alert Deduplication & Risk Scoring Engine             │
│   └── Case Management / SOAR Webhook Ingestion              │
└─────────────────────────────────────────────────────────────┘
```

#### Transpilasi dan Abstraksi Deteksi (pySigma Internals)
Sistem Detection-as-Code memanfaatkan *Intermediate Representation* (IR) abstrak. Aturan Sigma diurai menjadi Abstract Syntax Tree (AST):
1. **Rule Parsing**: File YAML diubah menjadi node evaluasi logika (AND, OR, NOT, Wildcards).
2. **Field Mapping & Conversion**: Nama field generik (misal: `CommandLine`) dipetakan ke field spesifik sistem tujuan melalui backend pipeline (misal: `process.command_line` pada Elastic ECS atau `CommandLine` pada Sysmon/Splunk).
3. **Target Query Generation**: AST dievaluasi dan dikompilasi ke format query target secara natif, meminimalisir deviasi logika antar platform.

#### Korelasi Stateful vs Stateless Detection
- **Stateless Detection**: Mengevaluasi event tunggal secara terisolasi. 
  Contoh: Eksekusi `mimikatz.exe` atau modifikasi registry kunci run. Evaluasi terjadi secara $O(1)$ terhadap stream event.
- **Stateful Detection (Complex Event Processing / CEP)**: Mengevaluasi jendela waktu (*sliding window*) atau rentetan urutan aksi (*sequence of operations*).
  Contoh: Penetrasi Pass-the-Ticket, di mana terjadi anomali permintaan Kerberos TGS diikuti oleh eksekusi proses bernilai tinggi (`lsass.exe` injection) dalam rentang waktu $\Delta t \le 300\text{s}$ dari IP/Host yang sama. Stateful detection membutuhkan penyimpanan state sementara (in-memory sliding window pada Redis atau memory state backend Apache Flink).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Legacy SIEM) | Pendekatan Modern Detection-as-Code (Enterprise) |
| :--- | :--- | :--- |
| **Penyimpanan Rule** | Tersimpan langsung di database GUI SIEM tanpa versioning. | Tersimpan dalam repository Git terpusat (Immutable, Version Controlled). |
| **Siklus Pengujian** | Ditulis langsung di produksi; pengujian manual saat insiden terjadi. | Validasi otomatis via pipeline CI/CD menggunakan automated unit tests dan live emulation. |
| **Portabilitas** | Terkunci pada sintaks vendor (*Vendor Lock-in* Splunk SPL, Elastic DSL, Sentinel KQL). | Agnostik vendor menggunakan standard Sigma/YARA-L; dapat ditranspilasi ke berbagai backend. |
| **Change Management** | Perubahan manual tanpa review, rawan human error dan silent break. | Peer review via Pull Request (PR), automated linting, approval chain terdokumentasi. |
| **Skalabilitas** | Query SIEM periodik terjadwal membebani disk SIEM (high I/O read load). | Event stream processing memvalidasi deteksi secara realtime saat event masuk (in-memory). |

---

### 5. How (Workflow Detail)

Alur kerja operasional end-to-end dari perancangan hingga deployment deteksi:

```
[Threat Modeling] ──> [Sigma Rule Authoring] ──> [Static Analysis (Linter)]
                                                        │
[SIEM/EDR API] <── [Staging Deployment] <── [Rule Transpilation]
      │
      ▼
[Atomic Red Team Emulation] ──> [Verification: Alert Fired?]
                                        │ (Yes)
                                        ▼
                             [Production Deployment]
                                        │
                                        ▼
                             [Continuous Telemetry Monitoring]
```

1. **Threat Modeling & Data Mapping**: Identifikasi taktik/teknik penyerang (misal: T1059.001 - PowerShell Obfuscation). Konfirmasi ketersediaan telemetri (misal: Windows Event ID 4104 - Script Block Logging).
2. **Sigma Rule Authoring**: Buat aturan deteksi terstruktur dalam format YAML yang mencakup kondisi deteksi, field mapping, tingkat keparahan, dan tag MITRE.
3. **Static Analysis & Validation (CI)**: Pipeline menjalankan linting schema, pengecekan konsistensi penamaan, validasi regex, dan pengecekan redundansi terhadap library aturan yang ada.
4. **Transpilation**: Engine `pySigma` mengompilasi file Sigma menjadi format query target (Splunk, Elastic, Sentinel).
5. **Integration & Adversary Emulation Testing**:
   - Deployment aturan ke staging SIEM/index secara terisolasi.
   - Eksekusi automated payload menggunakan Atomic Red Team atau harness pengujian kustom.
   - Pengecekan via API: Apakah alert muncul dalam waktu toleransi ($T < 60\text{s}$)? Apakah field hasil parsing sesuai?
6. **Production Deployment & Monitoring**: Rule dideploy ke tenant produksi via REST API. Metrik performa rule (execution time, EPS scanned, false positive rate) dimonitor secara berkala.

---

### 6. Analogy & Diagram ASCII

#### Analogi Pabrik Perakitan Otomotif & Crash Test
Mengelola deteksi keamanan sama seperti merakit mobil di pabrik modern. 
- Menulis rule langsung di SIEM produksi sama seperti **membuat komponen rem langsung di jalan raya saat mobil berkecepatan 120 km/jam**. Jika rem gagal, kecelakaan fatal terjadi.
- **Detection-as-Code** adalah pabrik otomatis: Blueprint rem dirancang dengan CAD (Sigma YAML), divalidasi toleransinya oleh simulator (Linter & Transpiler), dibuat dalam prototipe lalu diuji tabrak di fasilitas uji (*crash test dummy* = Atomic Red Team). Setelah lolos uji keselamatan tanpa cacat, komponen rem dipasang ke jalur produksi massal.

#### Diagram Interaksi Transpilasi & Testing DaC
```
+---------------------------------------------------------------------------------+
|                               DEVELOPMENT REPO                                  |
|  rules/windows/process_creation/proc_creation_win_susp_powershell_download.yml  |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                             CI/CD ENGINE (Runner)                               |
|                                                                                 |
| 1. LINT: sigma-cli check                                                        |
|    PASS: Schema Valid, UUID Unique, MITRE Tag Present                           |
|                                                                                 |
| 2. COMPILE: pySigma Backend                                                     |
|    Output Target: Elastic Query DSL                                             |
|    { "query": { "bool": { "must": [ ... "powershell.exe", "DownloadString" ] }}}|
|                                                                                 |
| 3. TEST DEPLOY: Inject rule to SIEM-Staging Cluster via API                     |
|                                                                                 |
| 4. ATTACK SIMULATION: Run Target Runner (T1059.001 Payload)                      |
|    Payload: powershell.exe -NoP -Command "(New-Object Net.WebClient)..."        |
|                                                                                 |
| 5. ASSERTION: Polling SIEM API for match within 120s                            |
|    RESULT: True Positive Alert Captured [Status: SUCCESS]                      |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                       PRODUCTION REPOSITORIES & SIEM/EDR                        |
|                     Rules Active Across Enterprise Fleet                        |
+---------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Deteksi Masquerading Ekstensi Ganda (Sigma Format)

Aturan ini mendeteksi upaya eksekusi file executable yang menyamar menggunakan ekstensi ganda (misal: `invoice.pdf.exe`).

```yaml
title: Suspicious Double Extension File Execution
id: 3d508e6f-42e7-4f9e-bc43-85b5e7d5a001
status: production
description: Mendeteksi eksekusi file biner yang menggunakan ekstensi ganda dokumen tipuan untuk mengelabui pengguna.
references:
    - https://attack.mitre.org/techniques/T1036/007/
author: Enterprise SecOps Detection Team
date: 2024-03-30
tags:
    - attack.defense_evasion
    - attack.t1036.007
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith:
            - '.pdf.exe'
            - '.docx.exe'
            - '.xlsx.exe'
            - '.txt.exe'
            - '.rtf.exe'
            - '.zip.exe'
    condition: selection
falsepositives:
    - Perangkat lunak legacy internal dengan skema penamaan file yang buruk (sangat jarang).
level: high
```

---

#### 7.2. Practical Example (Production-Grade Detection-as-Code Pipeline)

##### File 1: Detection Engine Pipeline Script (`build_and_deploy.py`)
Skrip Python enterprise untuk validasi, transpilasi, pendaftaran ke Elastic SIEM, dan pemicuan validasi testing.

```python
#!/usr/bin/env python3
"""
Enterprise Detection-as-Code Compiler & Deployer
Target Platform: Elastic Enterprise Search / Detection Rules API
"""

import os
import sys
import json
import logging
import requests
from pathlib import Path
from sigma.collection import SigmaCollection
from sigma.backends.elasticsearch import LuceneBackend
from sigma.pipelines.elasticsearch import ecs_windows

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DaC-Deployer")

ELASTIC_ENDPOINT = os.getenv("ELASTIC_ENDPOINT", "https://siem.enterprise.internal:9200")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")

class DetectionDeployer:
    def __init__(self):
        if not ELASTIC_API_KEY:
            logger.error("ELASTIC_API_KEY environment variable is missing.")
            sys.exit(1)
        
        self.headers = {
            "Authorization": f"ApiKey {ELASTIC_API_KEY}",
            "Content-Type": "application/json",
            "kbn-xsrf": "true"
        }
        # Inisialisasi Backend Sigma dengan ECS Pipeline
        self.backend = LuceneBackend(ecs_windows())

    def transpile_rule(self, rule_path: Path) -> dict:
        """Parse Sigma YAML and transpile to Elastic Query DSL/Lucene string."""
        with open(rule_path, "r", encoding="utf-8") as f:
            rule_content = f.read()
        
        collection = SigmaCollection.from_yaml(rule_content)
        queries = self.backend.convert(collection)
        
        rule_meta = collection.rules[0]
        
        return {
            "rule_id": str(rule_meta.id),
            "name": rule_meta.title,
            "description": rule_meta.description,
            "severity": rule_meta.level.name.lower() if rule_meta.level else "medium",
            "query": queries[0],
            "tags": [str(t) for t in rule_meta.tags]
        }

    def deploy_to_elastic(self, compiled_rule: dict) -> bool:
        """Upsert detection rule via Kibana/Elasticsearch Detection Rules API."""
        url = f"{ELASTIC_ENDPOINT}/api/detection_engine/rules"
        
        payload = {
            "rule_id": compiled_rule["rule_id"],
            "name": compiled_rule["name"],
            "description": compiled_rule["description"],
            "severity": compiled_rule["severity"],
            "type": "query",
            "query": compiled_rule["query"],
            "language": "kuery",
            "risk_score": 73,
            "enabled": True,
            "interval": "5m",
            "from": "now-6m",
            "tags": compiled_rule["tags"]
        }

        # Check existing rule
        find_url = f"{url}?rule_id={compiled_rule['rule_id']}"
        find_res = requests.get(find_url, headers=self.headers, verify=True)
        
        if find_res.status_code == 200 and find_res.json().get("total", 0) > 0:
            logger.info(f"Rule {compiled_rule['rule_id']} exists. Updating...")
            patch_url = f"{url}"
            payload["id"] = find_res.json()["data"][0]["id"]
            res = requests.patch(patch_url, headers=self.headers, json=payload, verify=True)
        else:
            logger.info(f"Rule {compiled_rule['rule_id']} new. Creating...")
            res = requests.post(url, headers=self.headers, json=payload, verify=True)

        if res.status_code in [200, 201]:
            logger.info(f"Successfully deployed: {compiled_rule['name']}")
            return True
        else:
            logger.error(f"Deployment failed for {compiled_rule['name']}: {res.status_code} - {res.text}")
            return False

def main():
    rules_dir = Path("./rules")
    if not rules_dir.exists():
        logger.error(f"Directory {rules_dir} not found.")
        sys.exit(1)

    deployer = DetectionDeployer()
    failed = False

    for file_path in rules_dir.glob("**/*.yml"):
        logger.info(f"Processing rule: {file_path.name}")
        try:
            compiled = deployer.transpile_rule(file_path)
            success = deployer.deploy_to_elastic(compiled)
            if not success:
                failed = True
        except Exception as e:
            logger.exception(f"Error processing {file_path}: {e}")
            failed = True

    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()
```

##### File 2: GitHub Actions Automated CI/CD Workflow (`.github/workflows/detection_pipeline.yml`)

```yaml
name: Detection Engineering CI/CD Pipeline

on:
  push:
    branches: [ "main" ]
    paths:
      - 'rules/**'
  pull_request:
    branches: [ "main" ]
    paths:
      - 'rules/**'

jobs:
  lint-and-validate:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Linting & Sigma Tools
        run: |
          python -m pip install --upgrade pip
          pip install yamllint sigma-cli pySigma pySigma-backend-elasticsearch

      - name: Validate YAML Syntax
        run: |
          yamllint -c .yamllint.yml rules/

      - name: Validate Sigma Rules Schema
        run: |
          sigma check --validation-config .sigma-validation.yml rules/

  emulation-test:
    needs: lint-and-validate
    runs-on: self-hosted-staging-runner
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Deploy Rules to Staging SIEM
        env:
          ELASTIC_ENDPOINT: ${{ secrets.STAGING_ELASTIC_ENDPOINT }}
          ELASTIC_API_KEY: ${{ secrets.STAGING_ELASTIC_API_KEY }}
        run: |
          python scripts/build_and_deploy.py

      - name: Execute Atomic Red Team Attack Simulation
        run: |
          pwsh -Command "Invoke-AtomicTest T1036.007 -TestNumbers 1 -TimeoutSeconds 60"

      - name: Assert Alert Generation
        env:
          ELASTIC_ENDPOINT: ${{ secrets.STAGING_ELASTIC_ENDPOINT }}
          ELASTIC_API_KEY: ${{ secrets.STAGING_ELASTIC_API_KEY }}
        run: |
          python scripts/verify_alert.py --rule-id "3d508e6f-42e7-4f9e-bc43-85b5e7d5a001" --wait-seconds 120

  deploy-production:
    needs: emulation-test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Deployment Dependencies
        run: |
          pip install pySigma pySigma-backend-elasticsearch requests

      - name: Deploy to Production SIEM Fleet
        env:
          ELASTIC_ENDPOINT: ${{ secrets.PROD_ELASTIC_ENDPOINT }}
          ELASTIC_API_KEY: ${{ secrets.PROD_ELASTIC_API_KEY }}
        run: |
          python scripts/build_and_deploy.py
```

##### File 3: Alert Verification Engine (`scripts/verify_alert.py`)

```python
#!/usr/bin/env python3
"""
Alert Assertion Script: Memvalidasi apakah event adversary emulation berhasil
memicu deteksi di SIEM dalam batas waktu SLA (Time-to-Detect Assertion).
"""

import os
import sys
import time
import argparse
import requests

def parse_args():
    parser = argparse.ArgumentParser(description="Verifikasi Assertion Alert Staging")
    parser.add_argument("--rule-id", required=True, help="UUID dari rule yang diuji")
    parser.add_argument("--wait-seconds", type=int, default=120, help="Maksimal waktu tunggu (detik)")
    return parser.parse_args()

def check_elastic_alerts(endpoint: str, api_key: str, rule_id: str) -> bool:
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "Content-Type": "application/json"
    }
    # Query Kibana Detection Engine Alerts index (.alerts-security.alerts-default)
    url = f"{endpoint}/api/detection_engine/signals/search"
    query = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"signal.rule.rule_id": rule_id}},
                    {"range": {"@timestamp": {"gte": "now-10m"}}}
                ]
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=query, verify=True, timeout=10)
        if response.status_code == 200:
            hits = response.json().get("total", 0)
            return hits > 0
    except requests.RequestException as e:
        print(f"[!] Request Exception saat query Kibana: {e}")
    return False

def main():
    args = parse_args()
    endpoint = os.getenv("ELASTIC_ENDPOINT")
    api_key = os.getenv("ELASTIC_API_KEY")

    if not endpoint or not api_key:
        print("[-] ELASTIC_ENDPOINT atau ELASTIC_API_KEY tidak dikonfigurasi.")
        sys.exit(1)

    print(f"[*] Menunggu deteksi rule ID: {args.rule_id} (Timeout: {args.wait_seconds} detik)...")
    interval = 10
    elapsed = 0

    while elapsed < args.wait_seconds:
        time.sleep(interval)
        elapsed += interval
        triggered = check_elastic_alerts(endpoint, api_key, args.rule_id)
        if triggered:
            print(f"[+] SUCCESS: Alert terpicu secara valid pada T+{elapsed} detik!")
            sys.exit(0)
        print(f"[*] Belum ada sinyal... (T+{elapsed}s)")

    print(f"[-] FAILED ASSERTION: Alert TIDAK terpicu setelah {args.wait_seconds} detik.")
    sys.exit(1)

if __name__ == "__main__":
    main()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Latar Belakang Insiden & Masalah
Sebuah institusi perbankan multinasional dengan infrastruktur **65.000 endpoint** dan volume log harian mencapai **18 Terabyte (rata-rata 110.000 EPS)** mengalami insiden *SOC Alert Fatigue* parah.
- **Gejala Masalah**: Rata-rata 14.500 alert per hari dihasilkan oleh sistem SIEM konvensional. 98,2% di antaranya adalah False Positive (FP) yang timbul dari script administrasi TI resmi, backup jobs, dan software deployment SCCM.
- **Dampak Fatal**: Serangan riil *Ransomware Precursor* berupa eksekusi BloodHound/Sharphound dan lateral movement via WMI terlewat (*silent breach*) selama 18 hari, berujung pada enkripsi data parsial di server non-produksi.

#### Implementasi Transformasi Engineering
Tim Detection Engineering enterprise melakukan refactoring menyeluruh selama 9 bulan:
1. **Migrasi ke Detection-as-Code Terpusat**: Semua rule ditarik dari GUI SIEM ke Git monorepo. Validasi otomatis diterapkan menggunakan GitHub Actions runners.
2. **Korelasi Stateful Stream (Apache Kafka + Flink Engine)**:
   - Log mentah disaring di edge layer (Fluentbit/Vector).
   - Event WMI execution (Event ID 4688/Sysmon 1) diproses di sliding window 5 menit pada Flink.
   - Deteksi tidak lagi hanya mencari eksekusi `wmic.exe process call create`, melainkan memverifikasi apakah akun yang mengeksekusi memiliki hak *Domain Admin* yang aktif login dari IP workstation non-standar (korelasi identitas via Active Directory streaming enrichment).
3. **Automated Canary Validation**: Menggunakan Atomic Red Team runner yang mengeksekusi controlled lateral movement payload setiap 24 jam untuk memverifikasi reliabilitas rule.

#### Hasil Terukur (Metrics & KPIs)

```
+------------------------------------+---------------------+---------------------+
| Metrik Performa Deteksi            | Sebelum Migrasi     | Sesudah Migrasi     |
+------------------------------------+---------------------+---------------------+
| Alert Volume per Hari              | 14.500 alert        | 112 alert           |
| False Positive Rate (FPR)          | 98,2%               | 3,1%                |
| Mean Time to Detect (MTTD)         | 432 Jam (18 Hari)   | 4,2 Menit           |
| Mean Time to Respond (MTTR)        | 36 Jam              | 14 Menit            |
| Coverage MITRE ATT&CK (Enterprise) | 18% (Unverified)    | 74% (CI-Asserted)   |
| Rule Breakage Incident per Bulan   | 14 insiden          | 0 insiden (Rollback)|
+------------------------------------+---------------------+---------------------+
```

---

### 9. Trade-offs (Analisis Arsitektur)

| Dimensi Arsitektur | Pilihan A: Centralized SIEM Query Pull | Pilihan B: Real-Time Stream CEP Engine | Justifikasi & Dampak |
| :--- | :--- | :--- | :--- |
| **Throughput & Latensi** | Latensi tinggi (polling batch interval 5–15 menit). | Latensi ultra-rendah (<1 detik via sliding window memory). | Stream processing unggul untuk deteksi real-time intrusi zero-day. |
| **Resource & Compute** | Beban berat pada storage I/O disk saat agregasi data historis. | Konsumsi Memory/RAM sangat tinggi untuk mempertahankan window state. | Stream engine membutuhkan kalkulasi sizing cluster RAM yang presisi. |
| **Kompleksitas Operasional**| Rendah: Hanya butuh konfigurasi query terjadwal di SIEM. | Sangat Tinggi: Membutuhkan orchestrator Kafka, Zookeeper/KRaft, dan Flink job cluster. | Memerlukan engineer berkualifikasi DevOps/Data Streaming tinggi. |
| **Biaya Lisensi / Infra** | Biaya ingest SIEM melonjak tinggi jika menelan raw noise log. | Biaya komputasi stream terprediksi; hanya alert/enriched log masuk SIEM. | Opsi B mereduksi *ingestion licensing cost* SIEM komersial secara drastis. |
| **Kapasitas Analisis Historis**| Sangat baik untuk audit forensik 90-365 hari ke belakang. | Kurang cocok untuk analisis masa lalu (fokus pada data in-motion). | Arsitektur ideal adalah **Hybrid**: Stream untuk CEP, Lake/SIEM untuk cold storage. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Brittle Regular Expression (Regex Fragility)
- **Kesalahan**: Menulis ekspresi deteksi command line yang terlalu presisi terhadap parameter urutan spasi atau tanda kutip, misalnya:
  `CommandLine: "powershell.exe -ExecutionPolicy Bypass -File script.ps1"`
- **Vulnerability**: Penyerang mengaburkan dengan permutasi urutan flag, spasi ganda, atau singkatan:
  `powershell.exe -ep bypass  -noni -f script.ps1`
- **Solusi**: Ubah parsing menjadi parameter-agnostik menggunakan tokenized matching:
  ```yaml
  detection:
      selection:
          Image|endswith: '\powershell.exe'
          CommandLine|contains|all:
              - '-ep' # atau bypass
              - '-f'
  ```

#### Kesalahan 2: Silent Rule Breakage Akibat Perubahan Skema Log
- **Masalah**: Vendor EDR atau OS melakukan upgrade versi yang mengubah nama field. Misal, `ParentCommandLine` berubah menjadi `parent_process.command_line`. Rule berhenti berfungsi (*silent failure*) tanpa ada peringatan error.
- **Troubleshooting & Remediasi**:
  1. Pasang skema contract validation pada CI pipeline menggunakan test suite data log sintetik (*Mock JSON Logs*).
  2. Gunakan pySigma mapping dynamic target dictionary, jangan hardcode nama field langsung di raw queries.
  3. Pantau metrik ingest telemetry per data-source secara continuous (`heartbeat monitor`).

#### Kesalahan 3: Missing State Purge pada Correlation Engine
- **Masalah**: State window korelasi pada Redis/Memory engine tidak memiliki Time-To-Live (TTL) yang dikonfigurasi dengan benar. Terjadi kebocoran memori (*memory exhaustion OOM crash*).
- **Troubleshooting**: Terapkan sliding window TTL terikat event time:
  ```python
  # Set key state dengan expiration otomatis
  redis_client.set(f"tracking:{src_ip}:{technique_id}", payload, ex=300) # Expire in 5 mins
  ```

---

### 11. Best Practices (Production Checklist)

#### Pre-Commit (Rule Authoring)
- [ ] Aturan memiliki UUIDv4 yang unik (`uuidgen`).
- [ ] Aturan mencakup referensi URL teknis yang valid dan taksonomi MITRE ATT&CK yang benar.
- [ ] Kolom `falsepositives` terdokumentasi secara detail dan spesifik, bukan deskripsi umum.
- [ ] Logic menghindari wildcard di awal string matching (misal: `*string`) pada database kolom berindeks B-Tree untuk mencegah query full table scan.

#### CI/CD Validation
- [ ] Linting lulus standar PEP8 (untuk engine) dan standard YAML linting.
- [ ] Transpilasi sukses tanpa warning/error ke seluruh sistem backend target (Elastic, Splunk, Wazuh).
- [ ] Unit test integrasi sukses dijalankan terhadap payload attack emulation di lingkungan staging.
- [ ] Assertions memastikan alert diproduksi dengan latency SLA yang diharapkan ($T < 60\text{s}$).

#### Production Monitoring & Governance
- [ ] Rule didaftarkan dengan status `testing` / canary selama 7 hari sebelum dinaikkan menjadi `production-blocking`.
- [ ] Metrik False Positive Rule dimonitor di dashboard internal; jika FP > 15%, auto-downgrade rule ke status tuning via ticket automation.
- [ ] Rule dievaluasi ulang setidaknya 6 bulan sekali terhadap modifikasi taktik penyerang (*Detection Drift*).

---

### 12. Hands-on Practice

Buat dan simpan file implementasi pada struktur direktori berikut:

```
hands-on/m02/
├── Makefile
├── rules/
│   └── proc_creation_win_mimikatz_minidump.yml
├── tests/
│   ├── test_vector_mimikatz.json
│   └── unit_test_runner.py
└── scripts/
    └── compile_sigma.py
```

#### Langkah 1: Siapkan Environment & Dependencies
Jalankan di shell:
```bash
mkdir -p hands-on/m02/rules hands-on/m02/tests hands-on/m02/scripts
cd hands-on/m02
python3 -m venv venv
source venv/bin/activate
pip install pySigma pySigma-backend-elasticsearch pytest pyyaml
```

#### Langkah 2: Buat Sigma Rule Target (`hands-on/m02/rules/proc_creation_win_mimikatz_minidump.yml`)
Rule untuk mendeteksi akses memori proses `lsass.exe` menggunakan comsvcs.dll:

```yaml
title: LSASS Memory Dump via Comsvcs DLL
id: 79796698-c116-4340-8547-498b3f2ecba2
status: production
description: Mendeteksi upaya eksekusi mini-dump LSASS menggunakan comsvcs.dll dan rundll32.exe.
references:
    - https://attack.mitre.org/techniques/T1003/001/
author: CyberSec Architect
date: 2024-03-30
tags:
    - attack.credential_access
    - attack.t1003.001
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith: '\rundll32.exe'
        CommandLine|contains|all:
            - 'comsvcs'
            - 'MiniDump'
    condition: selection
falsepositives:
    - Administrator troubleshooting crash memory (sangat tidak lumrah menggunakan comsvcs).
level: critical
```

#### Langkah 3: Buat Mock Test Data Telemetri (`hands-on/m02/tests/test_vector_mimikatz.json`)
```json
[
  {
    "description": "True Positive: Serangan MiniDump comsvcs standar",
    "event": {
      "process.executable": "C:\\Windows\\System32\\rundll32.exe",
      "process.command_line": "rundll32.exe C:\\Windows\\System32\\comsvcs.dll, MiniDump 624 C:\\temp\\lsass.dmp full"
    },
    "expected_match": true
  },
  {
    "description": "False Positive Avoidance: Eksekusi rundll32 normal tanpa argumen comsvcs",
    "event": {
      "process.executable": "C:\\Windows\\System32\\rundll32.exe",
      "process.command_line": "rundll32.exe shell32.dll,Control_RunDLL desk.cpl"
    },
    "expected_match": false
  }
]
```

#### Langkah 4: Buat Unit Test Runner Evaluator (`hands-on/m02/tests/unit_test_runner.py`)
```python
#!/usr/bin/env python3
import json
import re
from pathlib import Path
from sigma.collection import SigmaCollection
from sigma.backends.elasticsearch import LuceneBackend
from sigma.pipelines.elasticsearch import ecs_windows

def lucene_to_regex(query: str) -> re.Pattern:
    """Konversi sederhana Lucene Query hasil pySigma ke Regular Expression untuk Local Testing."""
    # Ekstraksi field: process.executable.text:"*\\rundll32.exe" AND process.command_line.text:*comsvcs*
    patterns = []
    
    # Matching process.executable
    if "rundll32.exe" in query:
        patterns.append(r".*rundll32\.exe$")
    if "comsvcs" in query and "MiniDump" in query:
        patterns.append(r".*comsvcs.*MiniDump.*")
        
    compiled_patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
    return compiled_patterns

def run_tests():
    rule_path = Path("rules/proc_creation_win_mimikatz_minidump.yml")
    test_data_path = Path("tests/test_vector_mimikatz.json")

    backend = LuceneBackend(ecs_windows())
    collection = SigmaCollection.from_yaml(rule_path.read_text(encoding="utf-8"))
    compiled_queries = backend.convert(collection)
    query_str = compiled_queries[0]
    
    print(f"[*] Transpiled Lucene Query:\n    {query_str}\n")
    
    with open(test_data_path, "r") as f:
        test_cases = json.load(f)

    regexes = lucene_to_regex(query_str)
    all_passed = True

    for idx, test in enumerate(test_cases):
        event = test["event"]
        exec_val = event.get("process.executable", "")
        cmd_val = event.get("process.command_line", "")
        
        # Evaluasi logika AND
        match_exec = any(r.match(exec_val) for r in regexes)
        match_cmd = any(r.match(cmd_val) for r in regexes)
        matched = match_exec and match_cmd

        if matched == test["expected_match"]:
            print(f"[PASS] Case {idx + 1}: {test['description']}")
        else:
            print(f"[FAIL] Case {idx + 1}: {test['description']} (Got {matched}, Expected {test['expected_match']})")
            all_passed = False

    if not all_passed:
        exit(1)
    print("\n[+] Seluruh unit tests lolos!")

if __name__ == "__main__":
    run_tests()
```

#### Langkah 5: Automasi Pipeline Menggunakan Makefile (`hands-on/m02/Makefile`)
```makefile
.PHONY: all lint test compile

all: lint test compile

lint:
	@echo "[*] Menjalankan linting rule..."
	sigma check rules/

test:
	@echo "[*] Menjalankan unit test asserting..."
	python3 tests/unit_test_runner.py

compile:
	@echo "[*] Transpilasi Sigma ke Elastic ECS query..."
	sigma convert -t elasticsearch -p ecs_windows rules/proc_creation_win_mimikatz_minidump.yml
```

Eksekusi pipeline lokal:
```bash
make all
```

---

### 13. Exercise

#### Level Easy
Tulis aturan deteksi Sigma (`rules/exec_whoami.yml`) untuk mendeteksi eksekusi tool recon dasar `whoami.exe` atau `whoami` pada Windows dan Linux.
- **Constraint**: Severity: `low`. Taktik: `Discovery (TA0007)`, Teknik: `T1033`. Pastikan lolos sintaks `sigma check`.

#### Level Medium
Buat modul korelasi python (`stream_correlation.py`) yang membaca stream JSON events via standard input (stdin) dan mendeteksi brute-force login SSH.
- **Spesifikasi**: Sinyal alert harus muncul bila terdeteksi lebih dari 5 kali `Failed password` dari alamat IP sumber (`source_ip`) yang sama dalam sliding window berdurasi 60 detik. Gunakan struktur data internal in-memory (misal `collections.defaultdict` dengan list timestamp).

#### Level Hard
Rancang arsitektur deteksi high-throughput untuk skenario komputasi cloud hybrid (AWS + On-prem).
- Tuliskan transpilasi parser pySigma backend custom kustom untuk mengonversi aturan deteksi Network Beaconing ke format AWS Athena SQL Query.
- Terapkan mekanisme penanganan false-positive dinamis: Query harus meng-exclude IP subnet CIDR internal yang terdaftar dalam file tabel lookup S3 secara otomatis via klausa `NOT IN (SELECT ip FROM internal_subnets)`.

---

### 14. Challenge

#### Deskripsi Skenario Tantangan Enterprise
Anda adalah Lead Detection Architect di unicorn Fintech. Perusahaan memiliki sistem database transaksi PostgreSQL inti yang menangani data PCI-DSS. Terjadi dugaan kebocoran data di mana seorang rogue engineer/penyerang menyusup dan melakukan eksfiltrasi bertahap (*slow and low data exfiltration*) dari database langsung ke internet via query SQL terselubung menggunakan DNS Exfiltration.

#### Kendala Operasional (Constraints)
1. **Volume Data Masif**: Server DNS internal mencatat traffic queries sebesar **80.000 DNS queries per detik (QPS)**. SIEM tidak mampu menampung seluruh raw payload logging DNS tanpa lonjakan biaya lisensi (miliaran rupiah/bulan).
2. **Karakteristik Ancaman**: Subdomain exfiltration dienkripsi/base32 dengan ukuran acak pendek (`< 32 bytes`) tiap record, dikirim tiap 10–30 detik (menghindari deteksi threshold volumetrik konvensional).
3. **Persyaratan Solusi**:
   - Rancang arsitektur stream enrichment di luar SIEM (menggunakan Kafka/Flink, Rust/Go binary, atau streaming vector).
   - Terapkan Shannon Entropy Calculation dan Kolmogorov-Smirnov distribution check terhadap nama subdomain secara streaming in-flight.
   - Buat algoritma transpilasi deteksi yang hanya mengekstrak alert berbobot tinggi ke SIEM tanpa membebani disk log indexer.
   - Siapkan skenario Automated Containment (SOAR) untuk melakukan isolasi host/user via API firewall jika skor anomali melampaui batas toleransi 0,89 selama lebih dari 3 menit berturut-turut.

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic (Pilihan Ganda & Singkat)
1. Apa fungsi esensial dari abstraksi Abstract Syntax Tree (AST) dalam arsitektur translasi pySigma?
2. Sebutkan kelemahan utama mengelola aturan deteksi keamanan secara manual langsung pada antarmuka GUI SIEM!
3. Pada level mana dalam *Pyramid of Pain* peran Detection-as-Code beroperasi paling efektif untuk memitigasi serangan?
4. Mengapa wildcard awal (leading wildcard, misal: `*cmd.exe`) sangat dihindari dalam authoring rule production-grade?
5. Apa perbedaan mendasar antara unit test deteksi statis (linting) dan dinamis (adversary emulation test)?

#### Soal Intermediate (Konseptual & Analitikal)
6. Jelaskan bagaimana sliding window time-to-live (TTL) pada streaming CEP engine mencegah eksploitasi race condition dalam serangan brute-force terdistribusi (*distributed password spraying*)!
7. Bagaimana arsitektur Detection-as-Code menangani inkonsistensi field antar log source (contoh: `TargetUserName` di Windows Security Event vs `user.target.name` di Elastic ECS)?
8. Jika sebuah canary rule di lingkungan staging tidak memicu alert saat adversary payload diinjeksikan oleh Atomic Red Team, sebutkan 3 titik evaluasi (debugging checklist) yang wajib diperiksa oleh detection engineer!
9. Jelaskan trade-off antara False Match Rate dan Processing Latency ketika mengimplementasikan deteksi Regex kompleks pada log network stream berkecepatan 100 Gbps!
10. Bagaimana arsitektur CI/CD rollback otomatis diterapkan jika rule deteksi yang baru saja di-*deploy* ke production menimbulkan lonjakan alert volume (alert storm) > 1.000 alert per menit?

#### Skenario Kasus Produksi
11. **Kasus 1**: Tim DevOps mengeluhkan bahwa aturan deteksi credential dumping berbasis kernel audit (`auditd`) pada klaster Kubernetes production mengakibatkan utilisasi CPU pada seluruh worker node melonjak dari 15% menjadi 92%. Lakukan analisis *root-cause* terhadap telemetri syscall auditd dan formulasikan solusi optimasinya tanpa menghilangkan visibilitas terhadap eksploitasi kontainer!
12. **Kasus 2**: Aturan deteksi Sigma untuk living-off-the-land binary (LOLBin) `certutil.exe -urlcache -split -f` memicu 300 False Positive per jam di subnet R&D Software Engineering akibat build script kompilasi internal. Bagaimana arsitektur penanganan *False Positive Suppression* dirancang agar tim engineering tidak terganggu, namun proteksi terhadap eksekusi malware nyata pada subnet finansial dan eksekutif tetap berjalan 100% ketat?
13. **Kasus 3**: Sebuah penyerang memanfaatkan taktik DLL Sideloading terhadap binary legitimate yang ditandatangani Microsoft (*Signed Binary*). Pipeline SIEM hanya memvalidasi integritas file (`Signature: Valid`). Rancang arsitektur deteksi komprehensif yang mampu mengidentifikasi malicious DLL injection tanpa mengandalkan validitas digital signature dari binary utama!

---

### 16. Summary

1. **Paradigma Detection-as-Code (DaC)**: Mentransformasi rekayasa deteksi keamanan dari operasi manual berbasis GUI menjadi disiplin software engineering modern yang menerapkan version control, modularitas, automated linting, transpilasi multi-target, dan testing berkelanjutan.
2. **Validasi Berkelanjutan via Adversary Emulation**: Rule deteksi tidak boleh diasumsikan berhasil sebelum diuji secara dinamis. Menggabungkan eksekusi payload emulasi (Atomic Red Team) ke dalam pipeline CI/CD menjamin reliabilitas deteksi terhadap variasi TTP penyerang.
3. **Streaming & Complex Event Processing (CEP)**: Menghadapi ledakan volume log enterprise, korelasi stateful secara real-time di message bus (Kafka/Flink) memberikan latensi deteksi sub-detik sekaligus mereduksi beban komputasi SIEM dan biaya lisensi ingest storage secara signifikan.
4. **Optimasi Signal-to-Noise Ratio (SNR)**: Keberhasilan arsitektur deteksi enterprise diukur dari efektivitasnya meminimalkan false positive. Kontekstualisasi identitas, pengecualian bersyarat (*suppression tuning*), dan dynamic baselining adalah kunci menjaga kewaspadaan tim SOC dari alert fatigue.