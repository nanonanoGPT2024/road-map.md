# BAB 09: Network Automation, NetDevOps, dan Programmability
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan arsitektur **Model-Driven Programmability** berbasis standar IETF dan OpenConfig menggunakan protokol gNMI/gRPC.
- Mengimplementasikan ekosistem **Network Infrastructure as Code (NetIaC)** berbasis GitOps dengan **Single Source of Truth (SSoT)** (NetBox/Nautobot).
- Mengintegrasikan pipeline Continuous Integration / Continuous Deployment (**CI/CD**) untuk jaringan dengan tahap pre-deployment validation menggunakan **Batfish** dan **pyATS/Genie**.
- Membangun pipeline **Streaming Telemetry** multi-vendor skala produksi menggantikan SNMP, dengan persistensi *time-series* dan visualisasi real-time.
- Menerapkan arsitektur **Event-Driven Automation (EDA)** untuk *auto-remediation*, *drift detection*, dan *closed-loop verification*.

---

### 2. Prerequisite
Untuk mengikuti modul ini dengan optimal, peserta wajib menguasai:
- Pengetahuan mendalam protokol switching dan routing enterprise/DC: BGP (eBGP/iBGP, Address Families, EVPN-VXLAN), OSPF, VLAN, VXLAN encapsulation.
- Pemahaman solid bahasa pemrograman Python 3.10+ (OOP, `asyncio`, typing, error handling).
- Penguasaan Git CLI (branching strategy, pull requests, merge conflict resolution).
- Pemahaman dasar REST API, serialization format (JSON, YAML), dan SSH transport level.
- Familiaritas dengan ekosistem container (Docker, Containerlab) dan Linux system administration.

---

### 3. Concept & Internal Architecture

#### 3.1 Model-Driven Programmability: YANG, NETCONF, RESTCONF, dan gNMI
Model-driven programmability memisahkan data modeling dari transport protocol. Inti dari arsitektur ini adalah **YANG (Yet Another Next Generation - RFC 6020/7950)**, bahasa pemodelan data struktural yang mendefinisikan hierarki konfigurasi, *operational state*, dan *RPC (Remote Procedure Calls)* perangkat jaringan.

```
+---------------------------------------------------------------+
|                       Data Model (YANG)                       |
|         - Native (Cisco-IOS-XE, Arista-EOS, Junos)            |
|         - OpenConfig (Vendor-neutral standard)                |
|         - IETF (RFC standard models)                          |
+---------------------------------------------------------------+
        |                               |                |
        v                               v                v
+----------------+              +---------------+ +-------------+
|    NETCONF     |              |   RESTCONF    | |    gNMI     |
| (RFC 6241/6242)|              |  (RFC 8040)   | |  (OpenConfig|
| XML over SSH   |              | JSON/XML over | | Protobuf/   |
| Synchronous    |              | HTTPS         | | gRPC/HTTP/2 |
+----------------+              +---------------+ +-------------+
```

##### Arsitektur Internal gNMI (gRPC Network Management Interface)
gNMI beroperasi di atas protokol transport **gRPC (HTTP/2)** dengan serialisasi biner **Protocol Buffers (Protobuf)**. Arsitektur internal gNMI memiliki 4 RPC inti:
1. `Capabilities`: Negosiasi kapabilitas model YANG dan versi encoding yang didukung target.
2. `Get`: Mengambil snapshot data konfigurasi atau operational state secara spesifik menggunakan gNMI path.
3. `Set`: Melakukan modifikasi atomik (*transactional update*, *replace*, atau *delete*) pada target datastore.
4. `Subscribe`: Menginisialisasi transmisi data telemetri stream secara persisten, mendukung mode:
   - `STREAM (ON_CHANGE)`: Data dikirim hanya jika terjadi transisi state pada node YANG yang diamati.
   - `STREAM (SAMPLE)`: Data dikirim secara periodik pada interval sampling berbasis nanodetik/milidetik.
   - `ONCE`: Pengambilan data sekali jalan mirip `Get` namun melalui stream subscriber.
   - `POLL`: Polling periodik melalui kontrol subscriber.

#### 3.2 Single Source of Truth (SSoT) Architecture
Dalam NetDevOps produksi, konfigurasi perangkat jaringan tidak boleh diedit langsung di CLI maupun didefinisikan secara statis di inventory file Ansible. SSoT bertindak sebagai representasi *intended state*. **NetBox** atau **Nautobot** memegang otoritas data state:
- IPAM (IP Address Management)
- DCIM (Racks, Devices, Cables, Interfaces)
- Tenancy, BGP Peering Sessions, VLAN allocation

Sinkronisasi SSoT ke jaringan bersifat searah: **SSoT $\rightarrow$ Pipeline Validation $\rightarrow$ Network Device**. *Operational state* yang ada pada perangkat yang tidak sesuai dengan SSoT diklasifikasikan sebagai **Configuration Drift**.

#### 3.3 Offline Pre-Flight Validation Engine: Batfish
Batfish mem-parsing konfigurasi perangkat jaringan multi-vendor (Cisco, Arista, Juniper, Cumulus) ke dalam format **Abstract Syntax Tree (AST)** internal, lalu memodelkan konvergensi control-plane (BGP, OSPF, static routes) secara virtual tanpa memerlukan Hypervisor/Emulasi hardware. Output yang dihasilkan berupa basis data relasional logis yang dapat di-query untuk membuktikan:
- Tidak adanya blackhole routing atau routing loop.
- Isolasi tenant (misal: *Customer A* tidak bisa mencapai prefix *Customer B*).
- ACL dan firewall reachability testing (*assertion-based verification*).

---

### 4. Why & What

| Dimensi | Legacy Network Engineering | Modern NetDevOps Enterprise |
| :--- | :--- | :--- |
| **Metode Modifikasi** | CLI scraping, interactive SSH manual, copy-paste terminal | Declarative API, Infrastructure as Code, CI/CD automated deployment |
| **Source of Truth** | Konfigurasi yang berjalan di perangkat (*running-config*) | Model tersentralisasi di Git repository dan IPAM/DCIM (NetBox) |
| **Validasi Perubahan** | Verifikasi manual post-maintenance (`ping`, `traceroute`, `show ip bgp`) | Offline Control-Plane validation (Batfish) + automated pre/post assertions (pyATS) |
| **Monitoring State** | Polling SNMP (UDP 161) periodik tiap 5 menit (CPU intensif) | Push Streaming Telemetry (gNMI/gRPC) berkecepatan sub-detik |
| **Rollback Strategy** | Menjalankan script pembatalan manual atau reload perangkat | Automated canary rollback berbasis git revert & commit atomic rollback |

---

### 5. How (Workflow Detail)

Alur kerja (workflow) implementasi NetDevOps produksi berjalan secara siklis dan terotomasi penuh:

```
[ Engineer / NetDevOps ]
           |
           v 1. Push Branch
[ Git Repo (GitLab/GitHub) ]
           |
           v 2. Trigger Webhook
[ CI Runner: Pre-Flight Stage ]
    +-------------------------------------------------------------+
    | a. Linting: yamllint, ruff, black                           |
    | b. SSoT Compilation: NetBox GraphQL -> Device Context Dict  |
    | c. Template Rendering: Jinja2 Context -> Candidate Configs  |
    | d. Offline Simulation: Batfish parsing & Assertions         |
    |    - Check BGP peering compatibility                        |
    |    - Check Reachability matrix                              |
    |    - Check no undefined VLANs/interfaces                    |
    +-------------------------------------------------------------+
           |
           v 3. Merge to 'main' & Deploy Approval
[ CD Runner: Deployment Stage ]
    +-------------------------------------------------------------+
    | a. Pre-Change Snapshot: pyATS captures RIB, BGP, ARP state  |
    | b. Atomic Push: gNMI Set (OpenConfig) / NETCONF Candidate   |
    | c. Commit Confirmation (Automatic rollback timer: 300s)     |
    | d. Post-Change Snapshot: pyATS captures current state       |
    | e. Diff Engine: pyATS validates RIB convergence without loss|
    | f. Commit confirmed: Deployment SUCCESS                     |
    +-------------------------------------------------------------+
           |
           v 4. In-Flight Failure Detected?
[ Automated Rollback Execution ] -> Restore checkpoint, notify Slack/PagerDuty
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Compiler Software vs NetDevOps Pipeline
Dalam rekayasa perangkat lunak modern:
`Source Code (Rust/C++)` $\rightarrow$ `Compiler (GCC/Clang)` $\rightarrow$ `Unit Testing` $\rightarrow$ `Binary Deployment`.

Dalam NetDevOps:
- **NetBox Data + Jinja2 Template** adalah *Source Code*.
- **Batfish / Pre-flight parser** adalah *Compiler & Static Code Analyzer*.
- **pyATS Testbed / Assertion Script** adalah *Integration Unit Tests*.
- **gNMI Set / Atomic Push** adalah *Deployment Artifact ke Host*.

#### Diagram Arsitektur Produksi NetDevOps

```
                     +---------------------------------------+
                     |         NetBox (DCIM / IPAM)          |
                     |         Single Source of Truth        |
                     +---------------------------------------+
                                         |
                                         | GraphQL / REST
                                         v
+------------------+         +-----------------------+         +------------------+
| Git Repository   |         |     CI/CD Engine      |         | Offline Engine   |
| - Jinja2 Tpls    |-------> |   (GitLab CI / GHA)   |<------->|    (Batfish)     |
| - Pipeline Rules |         +-----------------------+         +------------------+
+------------------+                     |
                                         | Telemetry Verification & Push
                                         v
                      +-------------------------------------+
                      |   Orchestration Layer (Python)      |
                      |   - gNMI Clients (pygnmi)           |
                      |   - pyATS / Genie Test Engine       |
                      +-------------------------------------+
                             |              |              |
                gRPC / gNMI  |  NETCONF/SSH |  gRPC/gNMI   |
                             v              v              v
                      +-------------+ +-------------+ +-------------+
                      | Spine-01    | | Spine-02    | | Leaf-01     |
                      | Arista EOS  | | Cisco IOS-XE| | Juniper vMX |
                      +-------------+ +-------------+ +-------------+
                             \              |              /
                              \   Streaming Telemetry     /
                               \  (gNMI ON_CHANGE)       /
                                v           v           v
                             +-------------------------------+
                             | Collector (Telegraf / Vector) |
                             +-------------------------------+
                                             |
                                             v
                             +-------------------------------+
                             | TSDB (Prometheus/VictoriaMetrics)
                             | Visualisasi: Grafana          |
                             +-------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Subscribing to gNMI Streaming Telemetry
Contoh skrip Python menggunakan library `pygnmi` untuk membaca operational state BGP neighbor secara realtime (*streaming*) menggunakan protokol gNMI.

```python
#!/usr/bin/env python3
"""
Simple Example: Menjalankan gNMI Subscribe Client untuk Telemetri Interface Arista/Cisco
Menggunakan format OpenConfig.
"""
from pygnmi.client import gNMIclient
import json

TARGET_ROUTER = {
    "host": "198.51.100.1",
    "port": 50051,
    "username": "admin",
    "password": "ProductionSecurePassword123!",
    "insecure": False,
    "path_cert": "/etc/ssl/certs/network-ca.pem"
}

# Path OpenConfig untuk statistik paket octet interface
INTERFACE_METRIC_PATH = [
    "/interfaces/interface[name=Ethernet1/1]/state/counters/in-octets"
]

def main() -> None:
    print(f"[*] Inisialisasi gNMI channel ke {TARGET_ROUTER['host']}...")
    with gNMIclient(
        target=(TARGET_ROUTER["host"], TARGET_ROUTER["port"]),
        username=TARGET_ROUTER["username"],
        password=TARGET_ROUTER["password"],
        path_cert=TARGET_ROUTER["path_cert"]
    ) as client:
        # Membuka subscription stream ON_CHANGE atau SAMPLE (interval: 5 detik)
        telemetry_stream = client.subscribe(
            subscribe={
                "subscription": [
                    {
                        "path": INTERFACE_METRIC_PATH[0],
                        "mode": "sample",
                        "sample_interval": 5_000_000_000  # 5 detik dalam nanodetik
                    }
                ],
                "mode": "stream",
                "encoding": "proto"
            }
        )

        print("[+] Terhubung. Menerima data streaming telemetri...")
        for packet in telemetry_stream:
            # Mengisolasi payload update
            if "update" in packet:
                update_data = packet["update"]
                print(f"[METRIC UPDATE] Timestamp: {packet.get('timestamp')}")
                print(json.dumps(update_data, indent=2))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Stream dihentikan oleh operator.")
```

---

#### 7.2 Practical Example: Enterprise Pre-Deployment Validation dengan Batfish
Implementasi sistem Python CI pipeline validation yang memverifikasi bahwa perubahan access-list (ACL) atau BGP routing tidak menyebabkan *unintended traffic isolation* atau *routing leakage*.

```python
#!/usr/bin/env python3
"""
Practical Production Example: Validasi Konfigurasi Sintaks & Routing State via Batfish
Kompatibel dengan runner CI/CD.
"""
from __future__ import annotations
import os
import sys
import logging
from pybatfish.client.session import Session
from pybatfish.datamodel.flow import HeaderConstraints
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("NetCI-Batfish")

BATFISH_HOST = os.getenv("BATFISH_HOST", "localhost")
SNAPSHOT_DIR = "./network-snapshot"
NETWORK_NAME = "enterprise-fabric-prod"
SNAPSHOT_NAME = "commit-stage-verify"

def initialize_batfish_session() -> Session:
    """Menginisialisasi session RPC Batfish Service."""
    logger.info(f"Menghubungkan ke service Batfish pada host: {BATFISH_HOST}")
    bf = Session(host=BATFISH_HOST)
    bf.set_network(NETWORK_NAME)
    bf.init_snapshot(SNAPSHOT_DIR, name=SNAPSHOT_NAME, overwrite=True)
    return bf

def test_syntax_parsing(bf: Session) -> bool:
    """Memverifikasi bahwa seluruh konfigurasi vendor ter-parse 100% tanpa error parsing fatil."""
    logger.info("[Test 1/3] Memeriksa Syntax Parser Errors...")
    result = bf.q.parseWarning().answer().frame()
    
    # Batfish menghasilkan log peringatan (warning) atau crash jika konfigurasi tidak valid
    if not result.empty:
        logger.warning("Ditemukan syntax warning dalam parsing snapshot:")
        print(result.to_string())
    
    # Periksa unresolved lines fatal
    init_issues = bf.q.initIssues().answer().frame()
    if not init_issues.empty:
        logger.error("FATAL: Konfigurasi gagal di-render oleh engine Batfish.")
        print(init_issues.to_string())
        return False
    
    logger.info("[PASS] Syntax parser valid.")
    return True

def test_bgp_session_compatibility(bf: Session) -> bool:
    """Membuktikan kompatibilitas sesi BGP (tidak ada mismatch AS, IP peering, atau auth)."""
    logger.info("[Test 2/3] Menguji BGP Session Compatibility...")
    bgp_status = bf.q.bgpSessionCompatibility().answer().frame()
    
    # Filter sesi yang statusnya bukan ESTABLISHED / UNIQUE_MATCH
    broken_sessions = bgp_status[bgp_status["Configured_Status"] != "UNIQUE_MATCH"]
    
    if not broken_sessions.empty:
        logger.error("Ditemukan miskonfigurasi sesi BGP:")
        print(broken_sessions[["Node", "Remote_Node", "Local_IP", "Remote_IP", "Configured_Status"]])
        return False
        
    logger.info("[PASS] Seluruh sesi BGP tervalidasi kompatibel secara matematis.")
    return True

def test_critical_service_reachability(bf: Session) -> bool:
    """
    Simulasi traceroute data plane.
    Memvalidasi bahwa 'Tenant-Web' dapat mencapai subnet 'Database-Cluster' pada port TCP 5432.
    """
    logger.info("[Test 3/3] Simulasi Data-Plane Path: Web Tier -> DB Tier...")
    
    # Definisi skenario paket sintetis
    headers = HeaderConstraints(
        srcIps="10.100.1.0/24",
        dstIps="10.200.2.10/32",
        ipProtocols=["TCP"],
        dstPorts="5432"
    )
    
    traceroute_result = bf.q.traceroute(
        startLocation="leaf-01[GigabitEthernet0/1]",
        headers=headers
    ).answer().frame()
    
    # Evaluasi status trace: ACCEPTED, DROPPED, LOOP
    traces = traceroute_result["Traces"].tolist()
    disposition_states = [trace[0].disposition for trace in traces if trace]
    
    if "DENIED_IN" in disposition_states or "DENIED_OUT" in disposition_states:
        logger.error("Security Policy Failure: Trafik Web -> DB terblokir oleh ACL/Firewall.")
        return False
        
    if "NULL_ROUTED" in disposition_states or "NO_ROUTE" in disposition_states:
        logger.error("Routing Failure: Trafik menuju DB mengalami blackhole/drop.")
        return False
        
    logger.info(f"[PASS] End-to-end data-plane flow valid. Disposisi: {disposition_states}")
    return True

def run_pipeline() -> None:
    try:
        bf = initialize_batfish_session()
        
        t1 = test_syntax_parsing(bf)
        t2 = test_bgp_session_compatibility(bf)
        t3 = test_critical_service_reachability(bf)
        
        if all([t1, t2, t3]):
            logger.info(">>> SELURUH VALIDASI PRE-FLIGHT BERHASIL. PIPELINE AMAN DILANJUTKAN KE DEPLOYMENT. <<<")
            sys.exit(0)
        else:
            logger.error(">>> PRE-FLIGHT PIPELINE GAGAL. PUSH KE PRODUKSI DIBATALKAN OTOMATIS. <<<")
            sys.exit(1)
            
    except Exception as exc:
        logger.critical(f"Kesalahan fatal selama eksekusi Batfish engine: {str(exc)}", exc_info=True)
        sys.exit(2)

if __name__ == "__main__":
    run_pipeline()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur 5-Stage Spine-Leaf Data Center (Global Financial Clearing)
- **Kondisi Awal:** Perusahaan multinasional mengelola 4 Data Center regional, masing-masing terdiri dari 32 Leaf dan 8 Spine switches. Konfigurasi dilakukan via script Ansible ad-hoc yang dieksekusi oleh 12 engineer dari laptop masing-masing tanpa SSoT tersentralisasi.
- **Insiden Kritis:** Seorang engineer mengunggah template Jinja2 dengan parameter BGP Community yang salah ke 16 border leafs. Akibatnya, prefix privat DC ter-redistribusi ke Internet upstream provider via AS-PATH prepend kosong. Terjadi kebocoran routing (*route leak*) global selama 47 menit, menyebabkan *packet interception* dan pinalti regulasi finansial sebesar $2.4M.

#### Desain Solusi Rekayasa
1. **NetBox Enterprise Integration:** Seluruh alokasi ASN, prefix BGP, dan interkoneksi kabel dikunci via NetBox API yang dilindungi role-based access control (RBAC). Setiap perubahan data di NetBox memicu webhook payload ke GitLab CI.
2. **GitOps Declarative Pipeline:** Repository Git menyimpan file template `.j2` dan policy-as-code Batfish. Developer tidak memiliki akses direct SSH/CLI ke production fabric.
3. **CI Validation Stage:**
   - Script Python melakukan parsing model via GraphQL NetBox.
   - Merender kandidat config OpenConfig.
   - Menjalankan Batfish session untuk memeriksa ribuan rute BGP. Jika ada prefix `RFC 1918` atau `Internal EVPN Route Type-5` yang lolos route-filter eBGP External, pipeline *exit 1* seketika.
4. **Automated Canary Deployment (Blue/Green Rollout):**
   - Perubahan hanya diaplikasikan pertama kali ke Leaf Pasangan 1 (Canary).
   - Verifikasi telemetri via gNMI: Jika drop counter interface melonjak > 0.01% atau BGP flapping > 0 dalam interval 5 menit pasca-push, gNMI client mengeksekusi *atomic revert* ke commit ID sebelumnya.
   - Jika metric stabil, peluncuran berlanjut ke seluruh Leaf dalam grup ketersediaan secara bertahap.

#### Hasil
- Zero route-leak incidents dalam 18 bulan pengoperasian.
- Waktu deployment perubahan BGP policy terpangkas dari 3 jam (manual review) menjadi 8 menit (full pipeline verification).
- Audit trail 100% terekam di Git commit history dan NetBox Change Logs.

---

### 9. Trade-offs

| Parameter | gNMI Streaming Telemetry | SNMPv3 Polling | GitOps Automated Push | Traditional Ad-Hoc Scripting |
| :--- | :--- | :--- | :--- | :--- |
| **CPU Overhead (Device)** | Sangat Rendah (Internal kernel hook / Protobuf native) | Sangat Tinggi (Walk tree traversal OID berkala via CPU) | N/A (Deployment phase) | Rendah saat eksekusi singkat |
| **Resolusi Data** | Sub-detik (Realtime on-change/event) | 1 s/d 5 Menit (Blind spot di antara polling window) | N/A | Terbatas pada point-in-time check |
| **Bandwidth Efisiensi** | Sangat Tinggi (Biner terkompresi Protobuf via HTTP/2) | Rendah (Payload UDP verbose, overhead parsing string) | N/A | N/A |
| **Kompleksitas Implementasi** | Tinggi (Butuh infrastruktur PKI, mTLS, proto compilation) | Sangat Rendah (Sudah tersedia di hampir seluruh platform legacy) | Sangat Tinggi (Memerlukan sistem CI/CD, SSoT, Testbeds) | Rendah (Cukup Python runner lokal) |
| **Risiko Human Error** | Minimal (Tervalidasi secara programatik) | N/A (Monitoring only) | Rendah (Perubahan diverifikasi Batfish sebelum push) | Sangat Tinggi (Typo manual, kurangnya determinisme) |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Mengabaikan Pengelolaan Certificate (mTLS) pada gNMI
- **Penyebab:** gRPC/gNMI secara default mewajibkan koneksi TLS terenkripsi mutual (mTLS). Seringkali engineer menggunakan self-signed cert tanpa konfigurasi `Subject Alternative Name (SAN)` yang cocok dengan FQDN/IP router.
- **Dampak:** Error `grpc._channel._InactiveRpcError: <_InactiveRpcError of RPC that terminated with status StatusCode.UNAVAILABLE: Failed to connect to remote host: Handshake failed>`.
- **Troubleshooting & Solusi:**
  Gunakan OpenSSL untuk memverifikasi SAN pada cert perangkat:
  ```bash
  openssl s_client -connect 198.51.100.1:50051 -showcerts </dev/null 2>/dev/null | openssl x509 -noout -text | grep -A 2 "Subject Alternative Name"
  ```
  Pastikan IP address atau FQDN perangkat tercantum dalam `IP Address:` atau `DNS:`. Pada client, pastikan root CA yang menandatangani certificate target dipassing secara eksplisit.

#### Mistake 2: Batfish Snapshot Folder Structure Mismatch
- **Penyebab:** Batfish mengharuskan struktur direktori yang sangat kaku. Jika struktur salah, Batfish tidak akan mengidentifikasi file teks sebagai konfigurasi perangkat jaringan.
- **Dampak:** Batfish melaporkan 0 node yang diproses tanpa memicu exception error yang jelas.
- **Troubleshooting & Solusi:**
  Pastikan struktur direktori snapshot mengikuti hirarki baku:
  ```
  network-snapshot/
  ├── configs/
  │   ├── spine-01.cfg
  │   ├── spine-02.cfg
  │   └── leaf-01.cfg
  ├── hosts/                 <-- (Opsional: untuk pemodelan host end-point)
  └── batfish/               <-- (Direktori internal auto-generated)
  ```

#### Mistake 3: Partial Configuration Commit pada Multi-Vendor Pipeline
- **Penyebab:** Menganggap perilaku commit setiap vendor identik. Arista EOS dan Cisco IOS-XR memiliki *candidate datastore* atomik dengan rollback otomatis, sementara Cisco IOS-XE (native legacy) mengeksekusi perintah baris-per-baris secara inkremental jika tidak menggunakan integrasi model NETCONF/YANG.
- **Dampak:** Perangkat masuk ke kondisi *half-configured* (misal: ACL sudah terpasang tapi IP interface gagal dikonfigurasi), menyebabkan pemutusan link remote management (*bricking remote access*).
- **Troubleshooting & Solusi:**
  Gunakan transaksi NETCONF `<commit-confirmed>` dengan parameter rollback time (misal 300 detik) atau gunakan gNMI `SetRequest` yang bersifat atomik across paths. Selalu sediakan *revert handler* di level pipeline wrapper.

---

### 11. Best Practices (Production Checklist)

#### Pre-Flight Checklist
- [ ] Model data didefinisikan secara deklaratif di SSoT (NetBox). Tidak ada *hardcoded variables* dalam Jinja2 templates.
- [ ] Schema linter lulus verifikasi tanpa parsing error (`yamllint`, `ruff`).
- [ ] Batfish memvalidasi tidak ada uncommitted route leaks, flapping BGP attributes, atau security drops pada jalur esensial.
- [ ] Kredensial, secret token, dan private keys disimpan aman dalam HashiCorp Vault / KMS; **dilarang keras** commit credentials ke repository Git.

#### In-Flight Deployment Checklist
- [ ] Gunakan fitur snapshot status operasional jaringan (Capture state: ARP table, MAC table, BGP Neighbor state, Routing table count) sebelum perubahan dieksekusi.
- [ ] Implementasikan safe commit token (misal: NETCONF `<confirmed/>` atau Arista `commit timer 5`).
- [ ] Terapkan perubahan bertahap berbasis *Failure Domains* (misal: Deploy Pod-1 Leaf, tahan 10 menit, verifikasi metrik telemetri, baru lanjut ke Pod-2).

#### Post-Flight Verification Checklist
- [ ] Tangkap snapshot operasional pasca-deployment menggunakan pyATS.
- [ ] Eksekusi diff profiling: pastikan $BGP_{established\_post} == BGP_{established\_pre}$ dan tidak ada rute penting yang hilang.
- [ ] Validasi metrik telemetri gNMI (Interface CRC errors, interface input/output drops, CPU utilization) tidak melebihi ambang batas (*threshold* normal).
- [ ] Konfirmasi commit (`<confirm/>`) dikirim ke router sebelum timer rollback kedaluwarsa.

---

### 12. Hands-on Practice

Tujuan: Membangun mini-fabric lab terotomasi dengan Containerlab, menjalankan audit konfigurasi menggunakan NetBox API dan Batfish, serta melakukan verifikasi deklaratif. Seluruh artefak akan disimpan dalam direktori `hands-on/m02/`.

#### Langkah 1: Setup Lingkungan Direktori
```bash
mkdir -p hands-on/m02/{topology,configs,scripts,snapshot/configs}
cd hands-on/m02/
```

#### Langkah 2: Buat File Topologi Containerlab (`topology/lab.clab.yml`)
Simulasi 2 Leaf dan 1 Spine menggunakan Arista cEOS atau Nokia SR Linux (contoh berikut berbasis cEOS multi-node):

```yaml
name: netdevops-m02

topology:
  nodes:
    spine01:
      kind: arista_ceos
      image: ceos:4.30.0F
      mgmt-ipv4: 172.20.20.11
    leaf01:
      kind: arista_ceos
      image: ceos:4.30.0F
      mgmt-ipv4: 172.20.20.21
    leaf02:
      kind: arista_ceos
      image: ceos:4.30.0F
      mgmt-ipv4: 172.20.20.22

  links:
    - endpoints: ["spine01:eth1", "leaf01:eth1"]
    - endpoints: ["spine01:eth2", "leaf02:eth1"]
```

#### Langkah 3: Definisikan Konfigurasi Dasar Perangkat
Buat konfigurasi baseline untuk Spine-01: Simpan di `snapshot/configs/spine01.cfg`

```text
hostname spine01
!
transceiver qsfp default-mode 4x10G
!
service routing protocols model multi-agent
!
vlan 1
!
interface Ethernet1
   no switchport
   ip address 10.0.0.1/30
!
interface Ethernet2
   no switchport
   ip address 10.0.0.5/30
!
interface Management1
   ip address 172.20.20.11/24
!
router bgp 65000
   router-id 10.255.255.1
   neighbor 10.0.0.2 remote-as 65001
   neighbor 10.0.0.2 description leaf01
   neighbor 10.0.0.6 remote-as 65002
   neighbor 10.0.0.6 description leaf02
   network 10.255.255.1/32
!
end
```

Buat konfigurasi Leaf-01: Simpan di `snapshot/configs/leaf01.cfg`

```text
hostname leaf01
!
service routing protocols model multi-agent
!
interface Ethernet1
   no switchport
   ip address 10.0.0.2/30
!
interface Loopback0
   ip address 10.255.255.11/32
!
router bgp 65001
   router-id 10.255.255.11
   neighbor 10.0.0.1 remote-as 65000
   network 10.255.255.11/32
!
end
```

Buat konfigurasi Leaf-02: Simpan di `snapshot/configs/leaf02.cfg`

```text
hostname leaf02
!
service routing protocols model multi-agent
!
interface Ethernet1
   no switchport
   ip address 10.0.0.6/30
!
interface Loopback0
   ip address 10.255.255.12/32
!
router bgp 65002
   router-id 10.255.255.12
   neighbor 10.0.0.5 remote-as 65000
   network 10.255.255.12/32
!
end
```

#### Langkah 4: Script Otomasi Validasi Batfish
Buat file `scripts/verify_fabric.py`:

```python
#!/usr/bin/env python3
from pybatfish.client.session import Session
import sys

def main():
    bf = Session(host="localhost")
    bf.set_network("lab-clab-fabric")
    bf.init_snapshot("snapshot", name="current", overwrite=True)

    print("[*] Memeriksa routing loop...")
    detect_loops = bf.q.detectLoops().answer().frame()
    if not detect_loops.empty:
        print("[!] TERDETEKSI ROUTING LOOP!")
        sys.exit(1)
    
    print("[*] Memeriksa peering BGP status...")
    bgp_status = bf.q.bgpSessionCompatibility().answer().frame()
    unmatched = bgp_status[bgp_status["Configured_Status"] != "UNIQUE_MATCH"]
    if not unmatched.empty:
        print("[!] Terdapat ketidakcocokan sesi BGP:")
        print(unmatched[["Node", "Remote_Node", "Local_IP", "Remote_IP", "Configured_Status"]])
        sys.exit(1)
        
    print("[SUCCESS] Fabric Snapshot 100% konsisten.")

if __name__ == "__main__":
    main()
```

#### Langkah 5: Eksekusi Praktikum
Jalankan container Batfish dan eksekusi skrip:
```bash
# Jalankan engine Batfish via Docker
docker run -d --name batfish -v batfish-data:/data -p 8888:8888 -p 9997:9997 -p 9996:9996 batfish/all-in-one

# Install client dependencies
pip install pybatfish pygnmi

# Jalankan pengujian offline
python3 scripts/verify_fabric.py
```

---

### 13. Exercise

#### Level Easy
Tuliskan satu skrip Python menggunakan library `pygnmi` yang melakukan operasi `Capabilities` RPC ke sebuah switch router dan mencetak daftar model YANG OpenConfig yang didukung beserta versinya ke layar terminal.

#### Level Medium
Buat sebuah script Jinja2 template (`leaf_bgp.j2`) yang menerima input struktur data dictionary Python:
```python
device_context = {
    "hostname": "leaf-tor-01",
    "asn": 65101,
    "spine_peers": [
        {"ip": "10.0.0.1", "remote_as": 65000, "bfd": True},
        {"ip": "10.0.0.5", "remote_as": 65000, "bfd": True}
    ],
    "evpn_af": True
}
```
Lalu buat skrip validasi assertions yang membuktikan jika `bfd` diset ke `True`, konfigurasi output wajib menghasilkan string `neighbor <ip> bfd`.

#### Level Hard
Buat custom Python pipeline stage untuk Batfish yang menguji skenario kegagalan:
Simulasikan pemutusan interface link fisik antara `spine01` dan `leaf01`. Jalankan kueri data plane Batfish untuk memastikan bahwa `leaf01` masih memiliki jalur alternatif (*multipathing / ECMP alternative*) untuk mencapai Loopback0 milik `leaf02` tanpa paket didrop (*zero packet loss under single link failure condition*).

---

### 14. Challenge

#### Skenario: Arsitektur Self-Healing Zero-Drift Fabric
Sebuah jaringan multi-tenant EVPN-VXLAN skala besar (200+ Nodes) sering mengalami insiden perubahan konfigurasi manual yang tidak terdokumentasi (*unauthorized out-of-band CLI changes*). 

**Tantangan Arsitektur:**
Rancang spesifikasi arsitektur teknis dan prototype automasi (end-to-end pseudocode / production Python script) yang berjalan secara kontinyu:
1. **SSoT Sync:** Menggunakan NetBox sebagai basis kebenaran data struktural.
2. **Drift Identification:** Secara periodik membaca running state via gNMI `Get` (format OpenConfig BGP / System) dan membandingkannya dengan state yang tersimpan di SSoT.
3. **Automated Remediator (Closed Loop):**
   - Jika terdeteksi konfigurasi liar (drift), automasi mengompilasi *anti-drift payload* (reverse patch).
   - Menjalankan Batfish validation secara in-memory untuk memastikan rollback/replace tersebut aman.
   - Mengaplikasikan `gNMI Set (Replace)` ke perangkat.
   - Mengirim alert post-mortem detail ke endpoint webhook Slack/Teams, mencakup *diff patch* dan user yang teridentifikasi melakukan pelanggaran via syslog.

*Kriteria Keberhasilan:* Sistem harus menyelesaikan deteksi dan remediate dalam tempo $< 60$ detik sejak modifikasi manual terjadi tanpa mengganggu traffic forwarding plane.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: 5 Pertanyaan Basic
1. Apa keunggulan teknis mendasar dari format serialisasi Protocol Buffers (Protobuf) pada gNMI dibandingkan encoding XML pada NETCONF?
2. Sebutkan perbedaan utama antara gNMI subscription mode `SAMPLE` dan `ON_CHANGE`!
3. Mengapa *running-config* pada router fisik **bukan** merupakan Single Source of Truth (SSoT) yang valid dalam metodologi NetDevOps modern?
4. Apa fungsi dari modul `parseWarning()` dan `initIssues()` pada platform Batfish?
5. Di layer manakah protokol gRPC beroperasi dalam model layer OSI/TCP-IP dan protokol transport apa yang mendasarinya?

#### Bagian B: 5 Pertanyaan Intermediate
1. Bagaimana cara gNMI menangani rollback konfigurasi jika salah satu path dalam `SetRequest` mengalami kegagalan validasi schema di sisi NOS (Network Operating System)?
2. Jelaskan mekanisme kerja Batfish dalam memodelkan protokol routing BGP tanpa melakukan boot-up terhadap OS perangkat aslinya!
3. Mengapa penggunaan Git branching model trunk-based development sering kali lebih dipilih dalam arsitektur CI/CD jaringan dibandingkan GitFlow tradisional?
4. Apa implikasi keamanan jika gNMI client berjalan tanpa memvalidasi Certificate Authority (`insecure=True`) di lingkungan produksi enterprise?
5. Bagaimana pyATS/Genie melakukan parsing data non-struktural CLI menjadi bentuk data terstruktur JSON schema-compliant?

#### Bagian C: 3 Skenario Kasus Produksi
1. **Skenario Pipeline Failure:** Sebuah pipeline deployment GitOps gagal pada tahap Batfish reachability analysis setelah seorang engineer menambahkan access-list baru. Log Batfish mencatat flow `10.10.10.0/24 -> 172.16.1.1:443` memiliki status `DENIED_IN`. Langkah investigasi root-cause apa yang harus dieksekusi engineer pada file ACL tanpa harus melakukan deployment ke router fisik?
2. **Skenario Telemetry Overhead:** Tim monitoring mengeluhkan CPU core switch melonjak hingga 100% pasca implementasi gNMI collector. Setelah diaudit, target subscription diset pada path `/interfaces/interface/state/counters` dengan sampling interval $10\text{ ms}$. Analisis apa yang keliru dari konfigurasi ini dan rancang konfigurasi koreksi yang optimal!
3. **Skenario SSoT Desynchronization:** Data IP address interface `Ethernet1/1` di router aktual adalah `10.1.1.1/30`, namun di NetBox tercatat `10.1.1.5/30`. Jika pipeline GitOps mengeksekusi metode deklaratif `Replace`, apa dampak yang akan terjadi pada konektivitas jaringan saat pipeline berjalan, dan bagaimana arsitektur pencegahan *pre-sync check* yang harus dibangun?

---

### 16. Summary

Modul ini telah mengupas tuntas transformasi rekayasa jaringan dari pendekatan CLI manual imperatif menuju metodologi **Model-Driven NetDevOps Enterprise**:
1. **Model-Driven Programmability:** Fondasi yang memisahkan format data melalui pemodelan standar (YANG OpenConfig/IETF) dan transmisi efisien berkecepatan tinggi berbasis HTTP/2 & Protobuf (gNMI/gRPC).
2. **GitOps & Single Source of Truth:** NetBox/Nautobot dan Git bertindak sebagai sentral kontrol kebenaran konfigurasi. Konfigurasi jaringan diperlakukan sama persis seperti source code software enterprise.
3. **Pre-flight Testing & Static Analysis:** Pemanfaatan engine simulasi offline seperti Batfish memungkinkan pembuktian matematis terhadap correctness konfigurasi data-plane dan control-plane sebelum artefak konfigurasi disentuhkan ke perangkat fisik/operasional.
4. **Reliability & Closed-Loop Telemetry:** Menggantikan polling SNMP konvensional dengan event-driven streaming telemetry berlatensi rendah untuk mewujudkan visibilitas granular, verifikasi pasca-deploy otomatis via pyATS, serta kemampuan auto-remediation terhadap configuration drift.