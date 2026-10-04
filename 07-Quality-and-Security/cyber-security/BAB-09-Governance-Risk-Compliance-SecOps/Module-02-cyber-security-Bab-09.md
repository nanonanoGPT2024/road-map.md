# Kurikulum Enterprise: Cyber Security
## Kategori: 07-Quality-and-Security
### BAB 09: Governance, Risk, Compliance (GRC) & SecOps
#### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Principal Security Engineer / Enterprise Security Architect diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur SecOps Skala Besar**: Membangun pipeline ingestion telemetri keamanan terdistribusi berbasis Kafka, ClickHouse/OpenSearch, dan Detection-as-Code engine yang mampu memproses minimal 100.000 Events Per Second (EPS).
2. **Mengeksekusi Continuous Compliance & Policy-as-Code**: Menerapkan validasi kepatuhan deterministik secara deklaratif menggunakan Open Policy Agent (OPA), Gatekeeper, dan Kyverno di sepanjang siklus hidup software delivery (Shift-Left & Shift-Right).
3. **Membangun Sistem Otomasi SOAR (Security Orchestration, Automation, and Response)**: Menulis *playbook* orkestrasi respons insiden nir-manusia (*zero-touch response*) untuk *threat containment* pada lingkungan hybrid-cloud dengan mempertahankan *Mean Time to Respond* (MTTR) di bawah 60 detik.
4. **Memetakan Kontrol Regulasi (PCI-DSS 4.0, SOC 2, ISO 27001:2022) ke Infrastruktur Kubernetes**: Mengotomatisasi audit trail berbasis bukti teknis (*evidence collection*) langsung dari event eBPF dan log audit cloud provider.

---

### 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut:
*   Pemahaman operasional Linux Kernel internals (khususnya *syscalls*, *cgroups*, *namespaces*, dan eBPF).
*   Pengalaman praktis mengelola cluster Kubernetes production (Admission Controllers, RBAC, NetworkPolicy).
*   Kemahiran pemrograman sistem dengan Go atau Python (tingkat lanjut), serta pemahaman format deklaratif Rego (OPA).
*   Pemahaman siklus CI/CD enterprise (GitHub Actions, GitLab CI, ArgoCD).
*   Selesai mempelajari *Module 01: Fundamental GRC & SecOps Frameworks*.

---

### 3. Concept & Internal Architecture

Implementasi modern SecOps dan GRC tidak lagi bergantung pada audit manual berbasis spreadsheet atau SOC berbasis ticketing konvensional. Pendekatan produksi enterprise mengadopsi model **Event-Driven Security Observability & Policy-as-Code Control Plane**.

```
                +-------------------------------------------------------+
                |           CONTINUOUS GOVERNANCE & GRC ENGINE          |
                |   - Threat Modeling Models (Stride/PASTA)             |
                |   - Regulatory Mapping Matrix (PCI-DSS, SOC2, ISO)    |
                |   - Evidence Gathering Engine (Read-only Scanners)   |
                +---------------------------+---------------------------+
                                            |
                                            v Policy Artifacts
+-----------------------------------------------------------------------------------------------+
|                                    POLICY-AS-CODE CONTROL PLANE                                |
|  [Dev Phase: conftest] ---> [Admission: Gatekeeper/OPA] ---> [Runtime: Falco / Tetragon eBPF] |
+-----------------------------------------------------------------------------------------------+
                                            |
                                            v Security Telemetry & Violation Signals
+-----------------------------------------------------------------------------------------------+
|                                SECOPS DISTRIBUTED PIPELINE                                    |
|                                                                                               |
|  [ Edge Nodes ] ---> [ Fluentbit / Vector ]                                                   |
|  [ Kube-Audit ] --->          |                                                               |
|  [ CloudTrail ] --->          v                                                               |
|                       [ Apache Kafka Message Broker (Topic Partitioned) ]                      |
|                               |                                                               |
|                               v                                                               |
|                     +-------------------+                                                     |
|                     | Detection Engine  | <--- [ Sigma / Yara / Custom Rego Rules ]           |
|                     | (Streaming Flink) |                                                     |
|                     +---------+---------+                                                     |
|                               | Alerts                                                        |
|                               v                                                               |
|                     +-------------------+                                                     |
|                     |    SOAR Engine    | ---> [ Containment: AWS API, Kubelet kill, WAF rule]|
|                     | (Workflow Worker) | ---> [ Notifications: OpsGenie, Slack, PagerDuty ]  |
|                     +---------+---------+                                                     |
|                               |                                                               |
|                               v                                                               |
|                 [ SIEM / Long-term Cold Storage ]                                             |
|                 (ClickHouse / OpenSearch / S3 WORM)                                           |
+-----------------------------------------------------------------------------------------------+
```

#### Komponen Internal Utama:

1. **Policy-as-Code Engine (Admission & Runtime)**:
   * **Admission Phase**: Mengintersepsi panggilan API server Kubernetes melalui Mutating & Validating Webhooks. OPA/Gatekeeper mengevaluasi *ConstraintTemplates* terhadap payload manifest YAML/JSON.
   * **Runtime Phase**: Menggunakan probe eBPF di kernel space (misalnya melalui Falco atau Tetragon) untuk memonitor eksekusi *syscall* kritis (`execve`, `ptrace`, `socket`, `openat`). Sinyal runtime diteruskan sebagai telemetry event real-time jika terjadi deviasi dari *security profile baseline*.

2. **Telemetry Ingestion & Stream Processing (SecOps Ingestion)**:
   * Event dari berbagai sumber (syslog, cloud audit, container engine, WAF) dinormalisasi ke format *Open Cybersecurity Schema Framework* (OCSF).
   * Apache Kafka bertindak sebagai buffer decoupling toleran kegagalan (*fault-tolerant*), mendistribusikan stream log ke Detection Engine (seperti Apache Flink atau Rule Engine internal) untuk *complex event processing* (CEP) dan korelasi temporal.

3. **Autonomous SOAR Engine**:
   * Komponen berbasis worker pool yang mengeksekusi Directed Acyclic Graph (DAG) state machines.
   * Menerapkan pola *Idempotent Execution*: Setiap aksi remediasi (misalnya mengisolasi IP penyerang di firewall perimeter, mencabut kredensial IAM yang bocor, atau mengkarantina pod yang disusupi) dapat dieksekusi berulang kali tanpa merusak state sistem infrastruktur.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise Continuous SecOps & GRC |
| :--- | :--- | :--- |
| **Audit Compliance** | Audit tahunan, pengumpulan screenshot manual secara reaktif, dokumen statis (Excel/PDF). | **Continuous Evidence Collection**: Penilaian kepatuhan berjalan secara terprogram tiap commit kode dan runtime scan. |
| **Penerapan Kebijakan** | Standar keamanan didokumentasikan di wiki internal; bergantung pada review manual peer engineer. | **Policy-as-Code**: Aturan diuji secara otomatis di CI pipeline dan diblokir secara preventif di admission controller. |
| **Deteksi Ancaman** | SIEM tersentralisasi berbasis log batch dengan query interval (latensi 5–15 menit). | **Stream-based Real-time Detection**: Korelasi langsung in-flight menggunakan eBPF telemetry & streaming query (latensi < 1 detik). |
| **Respons Insiden** | Manual: Tiket Jira dibuat, eskalasi on-call engineer, troubleshooting manual via SSH. | **Automated SOAR Playbooks**: Isolasi terorkestrasi, *snapshot forensic* otomatis, dan rotasi kredensial instan. |

---

### 5. How (Workflow Detail)

Alur kerja implementasi produksi terbagi menjadi dua siklus yang saling bertautan:

#### Siklus A: Continuous Governance & Compliance (Shift-Left)
1. **Fase Authoring**: Tim Security menulis aturan kepatuhan dalam bentuk bahasa deklaratif (Rego) dan menyimpannya di repository Git khusus (*Policy-as-Code Repository*).
2. **Fase CI/CD Gate**:
   * Developer melakukan `git push` manifest Kubernetes atau Terraform.
   * CI Pipeline mengeksekusi `conftest` untuk memvalidasi konfigurasi terhadap modul Rego.
   * Jika terdapat pelanggaran severity level *HIGH* atau *CRITICAL* (misal: pod meminta privilege `CAP_SYS_ADMIN`), build langsung digagalkan (*break the build*).
3. **Fase Ingress Cluster (Admission Control)**:
   * API Server memicu Validating Webhook OPA Gatekeeper.
   * Kepatuhan divalidasi ulang di level runtime API untuk mencegah bypassing dari bypass direct-API access.
4. **Audit Loop**: OPA Audit Controller melakukan rekonsiliasi berkala untuk mendeteksi resource non-komplian yang ada sebelum policy dideploy (*drift detection*).

#### Siklus B: SecOps Telemetry to Response (Shift-Right)
1. **Event Capture**: eBPF driver menangkap event *syscall* berbahaya di level node worker (misal: `nsenter` dieksekusi di dalam container).
2. **Ingestion & Normalisasi**: Vector Agent mengumpulkan event, menyematkan metadata cluster/namespace/pod, dan mengirimkannya ke Kafka Topic `secops.alerts.raw`.
3. **Correlation**: Flink CEP memvalidasi apakah event runtime ini diikuti oleh network egress anomali ke IP Threat Intelligence.
4. **Trigger SOAR**: Jika kondisi terpenuhi, event dipublikasikan ke topic `secops.actions.execute`.
5. **Remediasi Otomatis**:
   * SOAR Worker mengonsumsi event.
   * Melakukan eksekusi NetworkPolicy darurat (*quarantine sandbox*).
   * Mengambil *memory dump* container untuk kebutuhan digital forensic.
   * Mematikan pod target (`SIGKILL`) dan menurunkan skala deployment jika terindikasi worm/lateral movement.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional Canggih
*   **GRC Policy-as-Code**: Peraturan keimigrasian dan keselamatan penerbangan internasional yang dicetak langsung menjadi firmware gerbang otomatis (E-Gate). Bukan hanya aturan di papan pengumuman, melainkan mesin tiket fisik yang tidak akan membuka pintu jika paspor tidak valid.
*   **SecOps Telemetry (eBPF)**: Jaringan kamera biometrik dan sensor x-ray berkecepatan tinggi yang terus mengawasi setiap lorong secara real-time.
*   **SOAR Engine**: Protokol darurat otomatis: jika seseorang melompati pagar perimeter, alarm menyala seketika, pintu kompartemen tertutup otomatis, dan security guard terdekat langsung diarahkan ke lokasi tanpa menunggu rapat direksi bandara.

#### Arsitektur Alur Data Runtime
```
 +------------------ POD EXECUTION SPACE --------------------+
 |                                                           |
 |  [ Attacker ] ---> Injects Reverse Shell via Exploit      |
 |                           |                               |
 |                           v                               |
 |                  syscall: execve("/bin/sh")               |
 +---------------------------|-------------------------------+
                             |
=============================v================================ KERNEL SPACE
 [ eBPF Ring Buffer (Tetragon / Falco Driver) ]
                             | (Zero-drop Kernel Event Trap)
=============================v================================ USER SPACE
 [ SecOps Telemetry Agent (DaemonSet) ]
     |
     | (gRPC / TLS 1.3 Mutually Authenticated)
     v
 [ Enterprise Message Bus (Apache Kafka Cluster) ]
     |
     +---> [ Stream Analytics / Complex Event Processor ]
     |         |
     |         v Threshold / Rule Matched (Critical Severity)
     +---> [ SOAR Controller Engine ]
               |
               +--- 1. Patch Kube-NetworkPolicy (Deny all egress)
               +--- 2. Trigger AWS GuardDuty / VPC Route Table Isolation
               +--- 3. Dump Memory & Pod Metadata to S3 Bucket
               +--- 4. Revoke IAM Token via STS AssumeRole Termination
               +--- 5. Notify Incident Responders (PagerDuty P1)
```

---

### 7. Practical Implementation

#### Implementasi 1: Production-Grade Policy-as-Code (Rego untuk OPA/Gatekeeper)
Validasi kepatuhan PCI-DSS 4.0 Sub-kebutuhan 2.2 (Konfigurasi Sistem Aman): Melarang container berjalan dengan privilege root dan membatasi `capabilities` Linux.

```rego
package kubernetes.admission.secops

import future.keywords.contains
import future.keywords.if
import future.keywords.in

default allow := false

# Entrypoint evaluasi admission
allow if {
    count(violation) == 0
}

# Blokir container yang tidak menetapkan runAsNonRoot = true
violation contains msg if {
    some container in input.review.object.spec.template.spec.containers
    not container_is_secure(container)
    msg := sprintf(
        "VIOLATION [PCI-DSS-4.0-Req-2.2]: Container '%v' dalam Deployment '%v' wajib mendefinisikan 'securityContext.runAsNonRoot: true'.",
        [container.name, input.review.object.metadata.name]
    )
}

# Blokir penambahan capability berbahaya (CAP_SYS_ADMIN, CAP_NET_ADMIN, CAP_ALL)
violation contains msg if {
    some container in input.review.object.spec.template.spec.containers
    some cap in container.securityContext.capabilities.add
    forbidden_capabilities[upper(cap)]
    msg := sprintf(
        "VIOLATION [CIS-K8S-5.2.8]: Container '%v' mencoba menambahkan dangerous capability '%v'. Penolakan absolut diberlakukan.",
        [container.name, cap]
    )
}

# Aturan eksplisit untuk kapabilitas terlarang
forbidden_capabilities := {
    "SYS_ADMIN",
    "NET_ADMIN",
    "ALL",
    "SYS_PTRACE",
    "DAC_OVERRIDE"
}

# Helper function untuk verifikasi runAsNonRoot
container_is_secure(container) if {
    container.securityContext.runAsNonRoot == true
}

container_is_secure(container) if {
    # Pod-level fallback validation
    input.review.object.spec.template.spec.securityContext.runAsNonRoot == true
    not container.securityContext.runAsNonRoot == false
}
```

*Unit Test untuk Policy di Atas (`policy_test.rego`):*
```rego
package kubernetes.admission.secops_test

import data.kubernetes.admission.secops.allow
import data.kubernetes.admission.secops.violation

test_deny_root_container if {
    manifest := {
        "review": {
            "object": {
                "metadata": {"name": "payment-api"},
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [{
                                "name": "web",
                                "securityContext": {"runAsNonRoot": false}
                            }]
                        }
                    }
                }
            }
        }
    }
    res := violation with input as manifest
    count(res) == 1
}

test_allow_secure_container if {
    manifest := {
        "review": {
            "object": {
                "metadata": {"name": "payment-api"},
                "spec": {
                    "template": {
                        "spec": {
                            "securityContext": {"runAsNonRoot": true},
                            "containers": [{
                                "name": "web",
                                "securityContext": {
                                    "capabilities": {"drop": ["ALL"]}
                                }
                            }]
                        }
                    }
                }
            }
        }
    }
    res := violation with input as manifest
    count(res) == 0
}
```

---

#### Implementasi 2: SOAR Incident Containment Engine (Python Async Worker)
Layanan automasi respons insiden yang menerima alert kritis dari Kafka, melakukan investigasi metadata, mengisolasi pod via NetworkPolicy, dan mencabut AWS IAM Role secara langsung.

```python
#!/usr/bin/env python3
"""
Enterprise SecOps Autonomous Containment Worker
Mengeksekusi tindakan mitigasi insiden level kritis secara idempotent.
"""

import asyncio
import json
import logging
import sys
from typing import Dict, Any
from kubernetes_asyncio import client as k8s_client, config as k8s_config
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - [%(name)s] - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("SOAR-Worker")

class SecurityRemediationEngine:
    def __init__(self):
        self.iam_client = boto3.client('iam')
        self.k8s_networking = None
        self.k8s_core = None

    async def initialize(self):
        """Memuat konfigurasi cluster Kubernetes internal."""
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            await k8s_config.load_kube_config()
        self.k8s_networking = k8s_client.NetworkingV1Api()
        self.k8s_core = k8s_client.CoreV1Api()
        logger.info("Kubernetes API async client terinisialisasi.")

    async def apply_zero_trust_quarantine(self, namespace: str, pod_name: str) -> bool:
        """
        Mengisolasi Pod yang disusupi dengan menerapkan Default-Deny NetworkPolicy
        secara selektif menggunakan label targeting.
        """
        quarantine_label = "secops.threat.containment"
        quarantine_policy_name = f"isolate-{pod_name}"

        try:
            # 1. Tambahkan label isolasi ke pod target
            patch_body = {
                "metadata": {
                    "labels": {quarantine_label: "true"}
                }
            }
            await self.k8s_core.patch_namespaced_pod(
                name=pod_name,
                namespace=namespace,
                body=patch_body
            )
            logger.info(f"Pod {pod_name} berhasil ditandai dengan label: {quarantine_label}=true")

            # 2. Buat NetworkPolicy isolasi total (Blokir Ingress & Egress)
            policy = k8s_client.V1NetworkPolicy(
                api_version="networking.k8s.io/v1",
                kind="NetworkPolicy",
                metadata=k8s_client.V1ObjectMeta(
                    name=quarantine_policy_name,
                    namespace=namespace,
                    labels={"managed-by": "secops-soar"}
                ),
                spec=k8s_client.V1NetworkPolicySpec(
                    pod_selector=k8s_client.V1LabelSelector(
                        match_labels={quarantine_label: "true"}
                    ),
                    policy_types=["Ingress", "Egress"],
                    ingress=[], # Array kosong = Blokir total incoming traffic
                    egress=[]   # Array kosong = Blokir total outgoing traffic
                )
            )

            await self.k8s_networking.create_namespaced_network_policy(
                namespace=namespace,
                body=policy
            )
            logger.warning(f"ISOLASI BERHASIL: NetworkPolicy '{quarantine_policy_name}' aktif pada pod '{pod_name}'.")
            return True

        except k8s_client.ApiException as e:
            if e.status == 409:
                logger.info(f"NetworkPolicy '{quarantine_policy_name}' sudah ada (Idempotent).")
                return True
            logger.error(f"Gagal mengisolasi Pod via K8s API: {e.reason}", exc_info=True)
            return False

    async def revoke_compromised_role(self, role_name: str) -> bool:
        """
        Menonaktifkan AWS IAM Role secara darurat dengan menyematkan
        inline deny-all assume policy session.
        """
        revoke_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Deny",
                    "Action": "*",
                    "Resource": "*"
                }
            ]
        }
        try:
            # Eksekusi blokir via botocore dalam thread executor (non-blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName="SOAR_EMERGENCY_DENY_ALL",
                    PolicyDocument=json.dumps(revoke_policy)
                )
            )
            logger.critical(f"KREDENSIAL DIAMANKAN: IAM Role '{role_name}' berhasil diputus hak aksesnya.")
            return True
        except ClientError as e:
            logger.error(f"Gagal mencabut AWS IAM Role: {e.response['Error']['Message']}")
            return False

    async def process_threat_event(self, event_payload: Dict[str, Any]):
        """Dispatcher parsing alert dan eksekusi mitigasi paralel."""
        severity = event_payload.get("severity", "LOW")
        rule_name = event_payload.get("rule_name")
        target = event_payload.get("target", {})

        logger.info(f"Menerima sinyal insiden: [{severity}] - {rule_name}")

        if severity == "CRITICAL":
            tasks = []
            if "pod_name" in target and "namespace" in target:
                tasks.append(
                    self.apply_zero_trust_quarantine(
                        namespace=target["namespace"],
                        pod_name=target["pod_name"]
                    )
                )
            if "iam_role" in target:
                tasks.append(
                    self.revoke_compromised_role(
                        role_name=target["iam_role"]
                    )
                )
            
            # Eksekusi aksi containment secara konkuen
            results = await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"Hasil eksekusi playbook penanganan: {results}")

# Entry point demonstrasi workflow
async def main():
    engine = SecurityRemediationEngine()
    await engine.initialize()

    # Simulasi payload deteksi dari Falco / Kafka CEP
    simulated_kafka_event = {
        "event_id": "evt-b09-9941a8",
        "severity": "CRITICAL",
        "rule_name": "Terminal_Spawned_Inside_Payment_Container",
        "target": {
            "namespace": "core-banking",
            "pod_name": "transaction-worker-7d6f54c96d-x89qp",
            "iam_role": "ProductionPaymentWorkerRole"
        }
    }

    await engine.process_threat_event(simulated_kafka_event)

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real World Case Study

#### Skenario: Skalabilitas GRC dan SecOps pada Bank Digital Transaksi Tinggi (PT Bank FinSecure)
*   **Profil**: 450+ microservices berjalan di 18 EKS Cluster multi-region, 65 juta event/hari, memproses 3.500 TPS pada jam sibuk.
*   **Masalah Utama**: 
    1. Kegagalan audit PCI-DSS 4.0 karena tim auditor eksternal menemukan drift konfigurasi IAM dan privilege pod tidak terkontrol secara konsisten.
    2. SOC Analyst mengalami kelelahan peringatan (*alert fatigue*): 14.000 alert per hari di SIEM berbasis Elastic, menghasilkan MTTR mencapai 4 jam 20 menit saat terjadi intrusi runtime.

#### Desain Solusi Arsitektural:
1.  **Shift-Left GRC via Policy Gates**:
    * Mengintegrasikan OPA/Gatekeeper di pipeline GitLab CI dan Kubernetes Control Plane.
    * Konfigurasi infrastruktur diwajibkan lolos 120 aturan compliance (CIS Benchmark 1.7 & PCI-DSS 4.0) secara statis sebelum di-apply oleh ArgoCD.
2.  **Streaming Detection & SOAR Implementation**:
    * Mengganti log streaming konvensional dengan driver eBPF runtime (Tetragon) yang diumpankan ke Apache Kafka (3-node cluster, retention 48 jam).
    * Mengimplementasikan Apache Flink untuk agregasi dan filtering alert duplikat, menurunkan volume event ke SIEM sebesar 92%.
    * Menghubungkan rule alert kritis ke *SOAR Worker* async berbasis Python/Go untuk karantina runtime tanpa campur tangan manusia.

#### Hasil dan Metrik Pasca-Implementasi:
*   **MTTR Penurunan Drastis**: Dari rata-rata 4 jam 20 menit menjadi **14 detik** untuk proses isolasi malware/reverse shell.
*   **Efisiensi Audit (GRC)**: Waktu persiapan audit PCI-DSS dipangkas dari 3 bulan per tahun menjadi **0 hari manual work** berkat *Continuous Automated Compliance Dashboard* berbasis bukti kriptografis Git commit dan eBPF telemetry trail.
*   **Pengurangan Biaya SIEM**: Volume ingest turun dari 12 TB/hari menjadi 1.1 TB/hari (hanya log bernilai tinggi), menghemat biaya storage data lake sebesar 74%.

---

### 9. Trade-offs & Engineering Decisions

```
+---------------------------------------------------------------------------------------------------+
| DIMENSI                       | PILIHAN A: IN-LINE HARD ENFORCEMENT | PILIHAN B: ASYNCHRONOUS AUDIT/EVENT  |
+-------------------------------+-------------------------------------+-------------------------------------+
| Performance & Latency         | Menambah overhead pada API Server   | Nol dampak pada p99 API Latency.    |
|                               | (+15-45ms pada setiap admission /   | Log diproses di luar alur eksekusi |
|                               | blocking syscall hook).             | utama (Out-of-band).                |
+-------------------------------+-------------------------------------+-------------------------------------+
| Resiko False Positives        | TINGGI. Bug pada policy Rego dapat  | RENDAH. Sinyal hanya menghasilkan   |
|                               | memblokir deployment produksi dan   | peringatan/tiket tanpa memutus flow |
|                               | melumpuhkan release pipeline.       | bisnis aplikasi.                    |
+-------------------------------+-------------------------------------+-------------------------------------+
| Risk Window (Exposure Time)   | NOL. Eksploitasi dicegah sebelum    | TERBUKA (Detik hingga Menit).       |
|                               | masuk ke environment runtime.       | Attacker memiliki window kecil      |
|                               |                                     | sebelum SOAR mengeksekusi isolasi.  |
+-------------------------------+-------------------------------------+-------------------------------------+
| Cost & Complexity             | Kompleksitas dependensi tinggi      | Memerlukan cluster Kafka, streaming |
|                               | (Webhook High Availability setup).  | compute, dan storage besar (SIEM).  |
+---------------------------------------------------------------------------------------------------+
```

#### Analisis Trade-off Storage SIEM (Hot vs. Warm vs. Cold):
*   **Hot Tier (NVMe SSD / In-Memory OpenSearch)**: Rentang 7-14 hari. Biaya per TB sangat tinggi, namun latency query < 500ms untuk kebutuhan investigasi aktif SOC.
*   **Warm Tier (Standard SSD / ClickHouse Object Storage Engine)**: Rentang 15-90 hari. Rasio kompresi 5:1, query membutuhkan 5-30 detik.
*   **Cold Tier (AWS S3 Glacier Instant Retrieval / GCS Archive)**: Rentang 91 hari - 7 tahun (kebutuhan audit PCI-DSS). Memerlukan katalogisasi metadata menggunakan Parquet/Athena untuk forensic on-demand dengan biaya terendah.

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal OPA Webhook Fail-Open vs Fail-Close
*   **Masalah**: Konfigurasi `ValidatingWebhookConfiguration` diset ke `failurePolicy: Fail` pada cluster dev/staging tanpa pod replikasi OPA yang memadai. Ketika node OPA restart, seluruh request API server K8s (termasuk pod critical kube-system) tertolak, menyebabkan cluster *bricked*.
*   **Solusi**:
    * Gunakan namespace selector eksklusi (`namespaceSelector.matchExpressions`) untuk `kube-system` dan `kube-public`.
    * Pasang *TopologySpreadConstraints* dan minimal 3 replika untuk Pod Gatekeeper/OPA.
    * Di staging awal, terapkan `failurePolicy: Ignore` (Fail-Open) dengan metrik alert webhook error rate.

#### 2. Event Dropping pada Driver eBPF under High Load
*   **Gejala**: SIEM kehilangan jejak proses singkat (*short-lived processes*) saat trafik transaksi melonjak.
*   **Root Cause**: eBPF *perf buffer* atau *ring buffer* di kernel mengalami starvation karena thread user-space consumer terblokir I/O throughput.
*   **Troubleshooting & Mitigasi**:
    * Monitor metrik kernel via `bpftool prog show` dan amati counter `drop_count`.
    * Naikkan ukuran alokasi `ring_buffer_pages` pada modul Tetragon/Falco.
    * Pin worker process collector ke core CPU khusus (*CPU Affinity*) untuk menghindari preemptive scheduling.

#### 3. SOAR Self-Inflicted Denial of Service (Death Spiral)
*   **Masalah**: SOAR Engine salah menginterpretasikan lonjakan traffic normal (misal load testing atau batch report) sebagai serangan DDoS, lalu secara otomatis mengisolasi subnet private node Kubernetes.
*   **Solusi Desain**: Terapkan mekanisme **Circuit Breaker** pada sistem automasi: batasi kuota tindakan destruktif (maksimal 5% dari total kapasitas Pod/Node dalam jendela 10 menit). Jika batas terlewati, de-eskalasi otomatis menjadi alert manual ke On-Call Incident Commander.

---

### 11. Best Practices (Production Checklist)

#### Governance & Continuous Compliance
- [ ] Aturan kepatuhan didefinisikan murni sebagai kode dalam repository Git terkontrol dengan validasi *Branch Protection* dan *Sign-off Security Owner*.
- [ ] Manifest Kubernetes, template Terraform, dan Dockerfile divalidasi deterministik menggunakan *conftest* / *trivy* di dalam pipeline CI/CD.
- [ ] Dilakukan rekonsiliasi berkala terhadap drift kepatuhan (OPA Gatekeeper `audit-interval: 60s`).
- [ ] Evidence collection berjalan non-intrusif dan disimpan di storage berstandar Write Once Read Many (WORM) yang tidak dapat dimanipulasi (*tamper-proof*).

#### SecOps & Incident Response
- [ ] Telemetri kernel divalidasi menggunakan eBPF untuk menghindari teknik obfuscation path pada log user-space auditd.
- [ ] Seluruh log telemetri dinormalisasi ke standar skema terbuka (misal OCSF).
- [ ] SOAR Playbook bersifat *idempotent* dan diverifikasi memiliki waktu eksekusi < 30 detik untuk mitigasi level Critical.
- [ ] Implementasi *Kill Switch* manual dan *Rate-Limiter Circuit Breaker* pada seluruh automation script mitigasi.
- [ ] Secret credentials, API keys, dan token IAM yang digunakan bot SOAR dirotasi otomatis maksimal setiap 90 hari menggunakan AWS Secrets Manager / HashiCorp Vault.

---

### 12. Hands-on Practice

Simulasi komprehensif implementasi Policy Gate dan Autonomous Incident Response.

Simpan seluruh file di direktori: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/policy
mkdir -p hands-on/m02/soar
```

#### Langkah 1: Siapkan Policy Admission K8s
Buat file `hands-on/m02/policy/compliance_policy.rego`:
```rego
package kubernetes.security

import future.keywords.contains
import future.keywords.if

default allow := false

allow if count(violations) == 0

violations contains msg if {
    input.kind == "Pod"
    some container in input.spec.containers
    container.securityContext.privileged == true
    msg := sprintf("Kepatuhan GRC Gagal: Container '%v' melanggar CIS-K8S Benchmark (Larangan privileged: true).", [container.name])
}
```

#### Langkah 2: Buat Test Manifest
Buat file `hands-on/m02/policy/pod_vuln.json`:
```json
{
  "kind": "Pod",
  "metadata": {"name": "crypto-miner"},
  "spec": {
    "containers": [
      {
        "name": "payload-runner",
        "image": "alpine:latest",
        "securityContext": {
          "privileged": true
        }
      }
    ]
  }
}
```

#### Langkah 3: Eksekusi Validasi Policy-as-Code via OPA Engine
Jalankan evaluasi CLI OPA:
```bash
# Install CLI opa jika belum tersedia
# curl -L -o /usr/local/bin/opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64 && chmod +x /usr/local/bin/opa

opa eval --data hands-on/m02/policy/compliance_policy.rego \
         --input hands-on/m02/policy/pod_vuln.json \
         "data.kubernetes.security.violations"
```
*Expected Output*: Muncul list pesan pelanggaran CIS-K8S Benchmark.

#### Langkah 4: Bangun Mock Simulator SOAR Response Playbook
Buat file `hands-on/m02/soar/mock_responder.py`:
```python
import sys
import json
import time

def execute_soar_containment(alert_data):
    print(f"[*] SOAR Engine menerima alert: {alert_data['alert_id']}")
    start = time.time()
    
    # Validasi kepatuhan severity
    if alert_data.get("severity") != "CRITICAL":
        print("[-] Alert bukan level CRITICAL. Bypass tindakan instan.")
        return

    # Langkah 1: Network Egress Disruption
    print(f"[!] Mengisolasi Pod: {alert_data['pod']} di Namespace: {alert_data['namespace']}...")
    time.sleep(0.5) # Simulasi patch network policy API call
    print("[+] Patch Applied: Ingress/Egress diset ke DENY-ALL.")

    # Langkah 2: Digital Forensic Preservation
    print(f"[!] Mengambil dump metadata runtime pod '{alert_data['pod']}'...")
    time.sleep(0.3)
    print(f"[+] Forensic Image berhasil disimpan ke s3://secops-evidence-vault/{alert_data['alert_id']}.json")

    elapsed = time.time() - start
    print(f"[SUCCESS] Insiden terminimalisir dalam {elapsed:.2f} detik. SLA < 60 detik TERPENUHI.")

if __name__ == "__main__":
    mock_alert = {
        "alert_id": "ALT-2024-eBPF-001",
        "severity": "CRITICAL",
        "namespace": "payment",
        "pod": "stripe-connector-5c79878d-k92lx",
        "signature": "Crypto_Wallet_Outbound_Communication"
    }
    execute_soar_containment(mock_alert)
```

Jalankan script:
```bash
python3 hands-on/m02/soar/mock_responder.py
```

---

### 13. Exercises

#### Level Easy
Tulis policy Rego sederhana yang memvalidasi bahwa setiap manifest `Deployment` di Kubernetes harus memiliki annotation mandatory compliance: `company.com/compliance-owner` dan `company.com/pci-scope` (`"in-scope"` atau `"out-of-scope"`).
*Acceptance Criteria*: Evaluasi OPA harus mengembalikan `violations` jika salah satu dari annotation ini tidak ditemukan di `metadata.annotations`.

#### Level Medium
Buat sebuah script Python pemantau Kafka (`kafka-python` atau `confluent-kafka`) yang berlangganan (*subscribe*) ke topic log keamanan `secops-raw-events`. Jika terdeteksi event dengan atribut `event.action == "aws:CreateAccessKey"` yang dilakukan oleh user non-whitelisted di luar jam operasional (08:00 - 18:00), script wajib mencetak pesan warning yang memformat payload aksi penonaktifan Access Key tersebut.
*Acceptance Criteria*: Parsing JSON stream non-blocking, verifikasi logika waktu, dan pencetakan command AWS CLI / boto3 call untuk menonaktifkan key.

#### Level Hard
Rancang dan implementasikan arsitektur *Dynamic Egress Lockdown* berbasis Go atau Python. Buatlah microservice yang mendengarkan event webhook alert. Ketika menerima notifikasi alert adanya file `.pcap` yang dieksfiltrasi dari sebuah namespace, service secara terprogram membuat resource CRD Kubernetes `NetworkPolicy` baru yang memblokir semua alamat IP egress kecuali domain internal DNS (`kube-dns`), lalu mengirimkan trace laporan JSON lengkap berisi checksum hash manifest ke S3 bucket yang memiliki proteksi *Object Lock* (WORM).
*Acceptance Criteria*: Teruji idempotent, menangani recovery logic ketika cluster API lambat, dan menyertakan skema verifikasi bukti kepatuhan integritas SHA-256.

---

### 14. Real-World Architectural Challenge

**Konteks Kasus**: Perusahaan Anda beroperasi di sektor FinTech Tier-1 yang tunduk pada pengawasan OJK, Bank Indonesia, dan PCI-DSS Level 1. Terjadi insiden Zero-Day pada library dependensi Java yang tersebar di 80+ microservices di dalam cluster EKS production multi-tenant.

**Situasi Lapangan**:
1. Patching source code dan rebuild image membutuhkan waktu estimasi minimal 48 jam kerja tim engineer.
2. Attacker saat ini secara aktif memindai eksternal endpoint dan mencoba mengeksekusi payload reverse shell berbasis perintah *bash socket*.
3. Sistem audit menuntut seluruh jejak bukti upaya intrusi dipertahankan tanpa modifikasi sedikitpun untuk kebutuhan pelaporan forensik regulator dalam waktu 3x24 jam sejak deteksi awal.

**Misi Anda (Tantangan)**:
Rancang dokumen arsitektur dan spesifikasi strategi *Emergency Defense-in-Depth* yang mencakup:
1. **Runtime Virtual Patching**: Bagaimana cara Anda mengonfigurasi probe eBPF (misalnya Falco/Tetragon) untuk mendeteksi *child process execution* dari engine Java dan memutusnya secara instan di level kernel space tanpa mematikan JVM container utama?
2. **Dynamic Ingress Shielding**: Bagaimana pipeline SecOps Anda secara otomatis menyebarkan rule pencegahan pola payload regex ke edge (Cloudflare WAF / AWS WAF) dalam hitungan detik setelah signature pertama tertangkap di satu node?
3. **GRC Audit Trail Preservation**: Susun alur penjaminan integritas bukti forensik digital (*Chain of Custody*) dari event stream log kernel yang dapat dibuktikan keasliannya di pengadilan / hadapan auditor independen tanpa risiko kontaminasi bukti.

*Sajikan desain dalam bentuk narasi teknis arsitektur mendalam, sequence diagram alur tanggap darurat, dan definisi aturan konseptual (kernel filter & WAF update).*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic
1. Apa perbedaan arsitektural utama antara Validating Admission Webhook dan Mutating Admission Webhook dalam konteks Policy-as-Code?
   * *Jawaban*: Mutating Webhook dieksekusi terlebih dahulu untuk mengubah atau melengkapi payload manifest (misal: menyuntikkan security sidecar atau default securityContext), sedangkan Validating Webhook dieksekusi setelahnya hanya untuk menerima atau menolak manifest secara biner berdasarkan aturan validasi tanpa mengubah konten resource.
2. Mengapa monitoring berbasis eBPF di SecOps jauh lebih tahan terhadap serangan evasif dibanding log user-space auditd standar?
   * *Jawaban*: eBPF beroperasi langsung di kernel space dan mengaitkan (*hook*) probe pada eksekusi internal kernel sebelum program user-space dapat memanipulasi, menyamarkan nama biner (obfuscation), atau menghapus file lognya sendiri di filesystem.
3. Apa fungsi utama retention WORM (Write Once, Read Many) dalam arsitektur kepatuhan GRC?
   * *Jawaban*: Mencegah modifikasi atau penghapusan data log/bukti audit oleh siapa pun (termasuk administrator sistem atau penyerang yang mengambil alih root credential) selama periode retensi yang ditentukan demi menjaga integritas barang bukti audit dan hukum.
4. Apa yang dimaksud dengan konsep *Detection-as-Code* dalam SecOps modern?
   * *Jawaban*: Pendekatan di mana aturan deteksi ancaman (seperti rule Sigma, Yara, atau Rego) diperlakukan layaknya software: ditulis dalam format deklaratif, disimpan di version control (Git), diuji via automated unit test di CI/CD, dan di-deploy secara otomatis ke SIEM/Detection Engine.
5. Sebutkan standar sub-kebutuhan kontrol PCI-DSS 4.0 yang mewajibkan isolasi jaringan dan pembatasan port/protokol yang tidak dibutuhkan!
   * *Jawaban*: PCI-DSS 4.0 Requirement 1 (Membangun dan Memelihara Keamanan Jaringan dan Konfigurasi Sistem Terkait).

#### Bagian 2: Intermediate
6. Bagaimana cara mencegah kondisi *split-brain* atau *race condition* ketika dua SOAR worker mencoba mengisolasi target pod yang sama secara bersamaan?
   * *Jawaban*: Menggunakan *Distributed Locking Mechanism* (misalnya via Redis Redlock atau etcd lease) atau mendesain aksi SOAR bersifat deterministik dan *idempotent* sehingga eksekusi berulang terhadap objek yang sama menghasilkan state akhir yang identik tanpa menghasilkan error atau kegagalan sistem.
7. Jelaskan risiko keamanan dari penggunaan OPA Gatekeeper dengan parameter `failurePolicy: Ignore` di lingkungan Kubernetes produksi!
   * *Jawaban*: Jika Gatekeeper mengalami *crash*, kehabisan memori (OOMKilled), atau jaringan webhook terputus, API Server akan tetap mengizinkan seluruh deployment masuk tanpa evaluasi keamanan, membuka celah bagi konfigurasi rentan atau pod berbahaya masuk ke cluster (*fail-open bypass*).
8. Mengapa Apache Kafka lebih disukai dibanding REST API langsung untuk mentransmisikan telemetri keamanan dari ribuan host ke SIEM/SOAR?
   * *Jawaban*: Kafka menyediakan *distributed buffering*, *backpressure handling*, toleransi kegagalan (*durability* via replication), dan kapabilitas pemrosesan paralel berbasis partisi, sehingga lonjakan trafik telemetri mendadak (bursty alerts) tidak akan menumbangkan server ingest SIEM downstream.
9. Bagaimana Anda mengonfigurasi OPA Rego agar tidak mengevaluasi pod-pod di namespace sistem seperti `kube-system` guna mencegah kegagalan fatal pada operasional inti cluster?
   * *Jawaban*: Dengan menambahkan filter pengecekan namespace pada level aturan Rego (misal: `input.review.object.metadata.namespace != "kube-system"`) atau lebih baik lagi, menyaringnya pada konfigurasi manifest Kubernetes `namespaceSelector` di `ValidatingWebhookConfiguration`.
10. Pada arsitektur SIEM terdistribusi, apa peran ClickHouse dibanding database transaksional konvensional (seperti PostgreSQL) dalam menangani data log telemetri?
    * *Jawaban*: ClickHouse adalah Column-Oriented DBMS yang dirancang khusus untuk analitik OLAP berskala besar. Ia menawarkan rasio kompresi data yang sangat tinggi (menghemat storage log), vector query processing berkecepatan tinggi, dan kemampuan memproses scan miliaran baris log per detik untuk audit trail forensic.

#### Bagian 3: Production Scenario Analysis
11. **Skenario 1**: SOC Engineer Anda mengimplementasikan playbook SOAR yang mematikan (*terminate*) pod saat mendeteksi adanya port scanning internal. Beberapa hari kemudian, saat update release berkala, seluruh pod dari sebuah service penting dihentikan berulang kali oleh SOAR hingga sistem down total. Apa akar penyebab arsitekturalnya dan bagaimana perbaikan desainnya?
    * *Analisis Akar Penyebab*: Playbook SOAR tidak memiliki konteks lingkungan (*lack of environment contextual awareness*). Komponen service discovery (seperti probe readiness/liveness internal Kubelet atau mesh network monitoring) disalahartikan sebagai aktivitas port scanning berbahaya karena rule deteksi terlalu dangkal (*false positive*).
    * *Solusi*: Terapkan *Whitelisting & Context-Aware Correlation*. Rule deteksi harus memvalidasi sumber IP pemanggil (apakah dari Kubelet CIDR atau authorized monitoring agent). Selain itu, pasang mekanisme *Circuit Breaker* pada SOAR yang mencegah terminasi jika pod yang terdampak melebihi persentase tertentu (misal > 20% kapasitas deployment) serta kirim alert investigasi ke manusia (*human-in-the-loop fallback*).

12. **Skenario 2**: Audit SOC 2 Type II menemukan bahwa selama 14 hari di kuartal ketiga, cluster staging enterprise memuat data kartu kredit riil dari database production tanpa enkripsi kolom yang sesuai standar. Tim developer berdalih staging diisolasi di private VPC. Bagaimana Anda sebagai Lead Security Architect menanggapi ini secara GRC dan solusi teknis apa yang wajib dipasang agar insiden ini tidak terulang?
    * *Tanggapan GRC*: Alasan isolasi private VPC **tidak dapat diterima**. Pelanggaran ini merusak postur Trust Services Criteria (TSC) pada aspek Confidentiality & Privacy. Penanganan data sensitif di lingkungan non-produksi melanggar regulasi dasar industri (PCI-DSS & SOC 2) terlepas dari arsitektur isolasi jaringannya.
    * *Solusi Teknis*:
      1. Terapkan pipeline *Automated Data Masking / Tokenization* (misalnya menggunakan tools sintetis atau masking proxy) sehingga data production yang disinkronisasi ke staging sudah disterilkan secara ireversibel.
      2. Pasang automated scanner berkala pada S3/Database di staging menggunakan tools Data Loss Prevention (DLP) untuk mendeteksi pola nomor kartu kredit (Luhn Algorithm pattern) dan membunyikan alarm audit jika ditemukan payload tidak tersamar.

13. **Skenario 3**: Tim DevOps mengeluhkan bahwa latensi API deployment ArgoCD mereka meningkat drastis dari 30 detik menjadi 8 menit setelah Gatekeeper dipasang di cluster dengan 200 ConstraintTemplate aktif. Setelah dianalisis, beban CPU API Server Kubernetes melonjak hingga 95%. Langkah optimasi arsitektur apa yang harus Anda ambil tanpa mengurangi standar kontrol keamanan?
    * *Langkah Optimasi*:
      1. **Evaluasi dan Optimasi Algoritma Rego**: Identifikasi query Rego yang memiliki kompleksitas $O(n^2)$ atau rekursi array berlebih (seperti iterasi multi-loop bersarang pada scanning container image/volumes). Ubah logic menjadi operasi himpunan (*set operations*) yang lebih hemat CPU.
      2. **Shift-Left Validasi ke Pipeline CI**: Pindahkan 80% aturan yang sifatnya statis (validasi label, larangan privileged, limits resource) dari Runtime Admission Webhook ke fase pra-commit/CI menggunakan `conftest`. Gatekeeper runtime hanya difokuskan pada aturan dinamis yang memerlukan konteks state cluster (misal: memvalidasi keunikan Ingress hostname).
      3. **Horizontal Pod Autoscaling & Resource Allocation**: Naikkan replikasi Gatekeeper controller pod dan pisahkan *audit pod* dari *admission webhook pod* agar proses periodic compliance background audit tidak mengonsumsi resource compute yang melayani traffic real-time API Server.

---

### 16. Summary

Modul ini telah menguraikan transformasi mendasar dari tata kelola keamanan reaktif konvensional menuju **Arsitektur Continuous GRC dan Autonomous SecOps**:
*   **GRC Modern adalah Kode Deklaratif**: Standar regulasi (PCI-DSS 4.0, SOC 2, ISO 27001) diejawantahkan secara konkret menjadi aturan-aturan logis (*Policy-as-Code*) menggunakan Open Policy Agent (OPA) dan Rego, yang memvalidasi integritas infrastruktur sejak fase build (CI) hingga admission control (CD).
*   **Observabilitas Runtime Berbasis eBPF**: Visibilitas keamanan runtime tidak lagi mengandalkan log teks user-space yang mudah dimanipulasi, melainkan menangkap sinyal *syscall* langsung dari kernel ring buffer, menghasilkan data telemetri dengan fidelity tinggi dan low overhead.
*   **Autonomous Response Menggantikan Tiket Manual**: Arsitektur stream processing (Kafka + Flink) yang dipadukan dengan worker automation (SOAR) memungkinkan pemotongan drastis waktu tanggap insiden (MTTR) dari skala jam ke hitungan detik melalui playbook karantina zero-touch yang teruji secara idempotent.
*   **Keseimbangan Reliabilitas dan Keamanan**: Penerapan sistem keamanan skala enterprise wajib mempertimbangkan trade-off operasional secara matang—mencegah insiden melalui circuit breaker, fail-safe webhook configuration, serta pemisahan tier penyimpanan forensik yang efisien.