# Module 01: Network Automation, NetDevOps, dan Programmability

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengidentifikasi batasan arsitektural dari *CLI screen scraping* dan beralih ke paradigma *model-driven programmability* berbasis API terstruktur.
- Mengembangkan skrip otomasi deterministik menggunakan pustaka Python `netmiko` untuk operasi perangkat warisan (*legacy*) dan `napalm` untuk abstraksi lintas vendor (*multi-vendor cross-platform abstraction*).
- Merancang dan merender konfigurasi jaringan berskala besar secara dinamis menggunakan mesin templat *Jinja2* yang terpisah dari struktur data (*data/template separation*).
- Mengorkestrasi perubahan status jaringan deklaratif menggunakan Ansible Network Modules (`cisco.ios`, `arista.eos`, `junipernetworks.junos`).
- Menganalisis dan mengimplementasikan protokol transmisi data *NETCONF* (RFC 6241) via SSH over port 830 dan *RESTCONF* (RFC 8040) over HTTP/2 / HTTPS.
- Menguraikan, memvalidasi, dan menyusun payload konfigurasi jaringan menggunakan *YANG Data Modeling* (RFC 6020 / RFC 7950) baik model native maupun OpenConfig.
- Membangun pipeline CI/CD lengkap untuk *Infrastructure as Code (IaC)* jaringan menggunakan Git, pengujian sintaks/kebijakan (*linting & dry-run*), validasi state berbasis *batfish/pyATS*, dan deployment otomatis.

---

## 2. Prerequisite
Untuk menyerap materi ini secara maksimal, peserta disyaratkan memiliki:
- Pemahaman mendalam tentang routing & switching enterprise/datacenter (BGP, OSPF, VLAN, VXLAN, ACL).
- Kemampuan pemrograman Python tingkat menengah (struktur data dictionary/list, OOP, penanganan exception, context manager, library virtualenv).
- Pemahaman protokol dasar TCP/IP stack: SSH, TLS/HTTPS, JSON, XML, dan YAML serialization.
- Familiaritas dengan Git workflow (branching, PR/MR, commit hashing) serta Linux CLI dasar.

---

## 3. Concept
Selama beberapa dekade, administrasi jaringan komputer bertumpu pada CLI (*Command Line Interface*) yang dioperasikan secara manual oleh manusia (*human-to-machine interaction*). Setiap vendor menciptakan sintaksis proprieter, format output yang tidak seragam, dan alur konfigurasi prosedural yang rentan terhadap *human error*. 

*Network Automation*, *NetDevOps*, dan *Programmability* merepresentasikan transformasi fundamental dalam pengelolaan infrastruktur jaringan:
1. **Network Programmability**: Membuka control-plane dan management-plane perangkat jaringan melalui API (*Application Programming Interface*) terbuka dan terstandarisasi, memungkinkan perangkat lunak berinteraksi langsung dengan perangkat keras secara terstruktur.
2. **NetDevOps**: Konvergensi filosofi DevOps ke dalam domain rekayasa jaringan. Prinsip intinya adalah menganggap jaringan sebagai perangkat lunak (*Network as Code*), di mana perubahan konfigurasi diperlakukan sebagai kode sumber yang harus melewati kontrol versi, pengujian otomatis, integrasi kontinu, dan deployment otomatis tanpa downtime.
3. **Model-Driven Management**: Paradigma di mana model data (ditulis dalam bahasa pemodelan YANG) menjadi *single source of truth* untuk mendefinisikan status perangkat (*state*) dan konfigurasi, menggantikan teks tidak terstruktur dari CLI output.

---

## 4. Why
Pendekatan tradisional manajemen jaringan via CLI manual memiliki kelemahan fatal di era cloud dan hyperscale datacenter:
- **Ketidakefisienan Operasional & Human Error**: Riset Gartner menunjukkan lebih dari 70% insiden *network downtime* disebabkan oleh kesalahan konfigurasi manusia (*fat-finger errors*) saat melakukan perubahan rutin.
- **Konfigurasi Drift (Configuration Drift)**: Perubahan ad-hoc di lapangan menyebabkan deviasi konfigurasi antar perangkat redundan, menghasilkan status jaringan yang tidak konsisten dan sulit di-troubleshoot.
- **Skalabilitas Nol**: Mengonfigurasi 500 switch fabric untuk deployment tenant baru memerlukan ratusan jam kerja insinyur jika dieksekusi per perangkat melalui konsol terminal.
- **Kurangnya Auditabilitas & Reproduksibilitas**: CLI manual tidak meninggalkan riwayat audit terpusat tentang siapa yang mengubah baris tertentu, mengapa perubahan tersebut dilakukan, dan bagaimana mengembalikan (*rollback*) status ke kondisi optimal sebelumnya secara instan jika terjadi anomali transmisi.

Adopsi NetDevOps memangkas *mean time to change* (MTTC) dari mingguan menjadi hitungan menit, dan meminimalkan *mean time to resolution* (MTTR) melalui verifikasi kondisi operasional terotomasi.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 CLI Scraping vs Structured API
| Parameter | CLI Screen Scraping (Legacy) | Structured API / Model-Driven |
| :--- | :--- | :--- |
| **Mekanisme** | Mengirim string perintah via SSH/Telnet, menangkap respons teks mentah (raw text). | Mengirim payload biner/terstruktur via RPC (Remote Procedure Call) atau REST. |
| **Parsing Data** | Regex (*Regular Expressions*), TextFSM. Sangat rapuh terhadap perubahan spasi, format output CLI, atau pembaruan firmware. | Native deserialization langsung ke objek JSON/XML/Protobuf. Struktur data sudah memiliki skema baku. |
| **Status Transaksi** | Prosedural. Gagal sebagian (*partial failure*) dapat membuat perangkat berada dalam status *broken state*. | Bersifat atomik (*ACID transactions*). Mendukung `candidate`, `confirmed-commit`, dan `rollback`. |
| **Autentikasi & Sesi** | SSH Terminal interactive shell login (TTY allocation overhead). | TLS/HTTPS mutual auth, token-based, atau Persistent SSH subsystem. |
| **Contoh Tooling** | `pexpect`, `Paramiko`, manual regex scripts. | `NETCONF`, `RESTCONF`, `gNMI`, Vendor SDK (e.g., Arista eAPI, Cisco NX-API). |

### 5.2 Python Ecosystem: Netmiko vs NAPALM
- **Netmiko**: Dibangun di atas `Paramiko`, secara spesifik dirancang untuk menangani keanehan CLI perangkat jaringan lintas vendor (menangani pagination `--More--`, timing prompt terminal, escalations privilege `enable`, handling banner). Netmiko mengeksekusi CLI scraping secara cerdas, namun output yang dihasilkan tetap berupa teks mentah kecuali diintegrasikan dengan *ntc-templates* (TextFSM).
- **NAPALM (Network Automation and Programmability Abstraction Layer with Multivendor support)**: Pustaka Python tingkat tinggi yang mengabstraksi fungsionalitas lintas platform. NAPALM menyediakan dua kapabilitas utama:
  1. *Getters*: Mengambil data operasional perangkat (`get_facts()`, `get_interfaces()`, `get_bgp_neighbors()`) dan mengembalikannya dalam skema dictionary Python yang identik, terlepas dari apakah targetnya adalah Cisco IOS, IOS-XR, Arista EOS, atau Juniper JunOS.
  2. *Configuration Management*: Mendukung operasi konfigurasi deklaratif: `load_merge_candidate()`, `load_replace_candidate()`, `compare_config()` (menghasilkan unified diff sebelum diterapkan), dan `commit_config()` / `discard_config()`.

### 5.3 Pemisahan Data dan Logika dengan Jinja2
Prinsip dasar otomatisasi modern adalah pemisahan antara konfigurasi logika (*template*) dan variabel status (*data model*).
- **Data (YAML/JSON)**: Menyimpan atribut jaringan murni (IP address, ASN, VLAN ID, Neighbor IP) tanpa sintaks vendor.
- **Template (Jinja2)**: Mengandung sintaks CLI spesifik vendor dengan penambahan placeholder, perulangan (`for`), dan logika kondisional (`if-elif-else`).
- Keuntungan: Penggantian perangkat keras ke vendor lain hanya membutuhkan pembaruan Jinja2 template tanpa perlu mengubah database variabel inventaris yang telah divalidasi.

### 5.4 Ansible Network Modules
Ansible menjalankan pendekatan *agentless* melalui SSH atau HTTP/REST. Berbeda dengan module Linux standar yang mengirim modul Python ke target (*managed node*), modul jaringan Ansible berjalan secara lokal di *Control Node*, memanggil API perangkat atau menjalankan CLI interaktif:
- Menggunakan modul berbasis koneksi jaringan: `ansible_connection: network_cli`, `ansible_connection: netconf`, atau `ansible_connection: httpapi`.
- Operasi Idempoten (*Idempotency*): Modul memeriksa apakah status perangkat saat ini (*current state*) sudah sesuai dengan status yang diinginkan (*desired state*). Jika sudah sama, Ansible tidak akan memicu perubahan (`changed=0`).

### 5.5 NETCONF & RESTCONF
- **NETCONF (RFC 6241)**:
  - Protokol berbasis XML yang beroperasi di layer transport SSH (port 830) menggunakan framing chunked.
  - Memisahkan konfigurasi ke dalam *Datastores*: `<running/>`, `<startup/>`, dan `<candidate/>`.
  - Memiliki kapabilitas manipulasi granular via RPC: `<get>`, `<get-config>`, `<edit-config>`, `<copy-config>`, `<commit>`, `<lock>`, `<unlock>`.
  - Mendukung transaksi atomik: Konfigurasi dikirim ke datastore `candidate`, di-diff, lalu dieksekusi secara instan ke `running` dengan fitur pengaman *confirmed commit* (jika sesi putus dalam kurun waktu tertentu, konfigurasi *rollback* otomatis).
- **RESTCONF (RFC 8040)**:
  - Pemetaan NETCONF ke paradigma RESTful API menggunakan HTTP verbs (GET, POST, PUT, PATCH, DELETE) dengan representasi payload JSON atau XML (`application/yang-data+json`, `application/yang-data+xml`).
  - Beroperasi di atas HTTPS standar (TCP port 443).
  - Struktur URI dipetakan secara deterministik dari modul YANG. Root resource secara umum berada di `/restconf/data/...` atau `/restconf/operations/...`.

### 5.6 Pemodelan Data dengan YANG (RFC 6020 / RFC 7950)
YANG (*Yet Another Next Generation*) adalah bahasa pemodelan data (*data modeling language*), bukan format serialisasi (seperti JSON/XML).
- Mendefinisikan hierarki, batasan (*constraints*), tipe data, dan semantik dari konfigurasi dan status operasional perangkat.
- **Node Types**:
  - `leaf`: Menyimpan nilai tunggal (e.g., nama antarmuka, MTU).
  - `leaf-list`: Array atau kumpulan nilai tanpa hierarki anak.
  - `container`: Mengelompokkan node-node terkait tanpa representasi list.
  - `list`: Kumpulan elemen identik yang diidentifikasi oleh satu atau lebih `key`.
- **Kategori Model**:
  - *Vendor Native Model*: Model yang diterbitkan oleh vendor spesifik (e.g., `Cisco-IOS-XE-native.yang`) yang mengekspos 100% fitur proprietary.
  - *Standardized / Open Models*: Model netral vendor yang diinisiasi oleh industri, terutama **OpenConfig** (`openconfig-interfaces.yang`, `openconfig-bgp.yang`) dan **IETF** (`ietf-interfaces.yang`).

### 5.7 CI/CD Pipeline untuk Perubahan Jaringan (NetDevOps)
Siklus hidup konfigurasi jaringan yang dimatangkan dalam alur kerja GitOps:
1. **Linting & Sintaks Validation**: Menguji validitas sintaks YAML, format Jinja2, dan skema YANG melalui tools seperti `yamllint`, `ansible-lint`, atau parser RFC.
2. **Pre-deployment Simulation (Digital Twin / Offline Validation)**: Memvalidasi konfigurasi terhadap topologi virtual menggunakan emulator (*Containerlab*, *Cisco CML*) atau mesin analisis data plane offline (*Batfish*) untuk membuktikan bahwa perubahan tidak menyebabkan *black hole*, *routing loop*, atau pelanggaran postur keamanan ACL sebelum menyentuh produksi.
3. **Automated Deployment**: Memicu pipeline via GitLab CI/GitHub Actions/ArgoCD untuk menerapkan *candidate configuration* via NETCONF/RESTCONF.
4. **Post-deployment Verification**: Memverifikasi operasional jaringan aktual (e.g., BGP neighbor status ESTABLISHED, packet drops == 0, ping latency baseline) via library assertion seperti `pyATS` atau `pytest`.
5. **Automatic Rollback**: Menginisiasi pembatalan otomatis jika pengujian pasca-perubahan mendeteksi deviasi Service Level Indicator (SLI).

---

## 6. How
Prosedur implementasi otomatisasi jaringan modern bertumpu pada tahapan terstruktur berikut:

```
[ Git Repository: Source of Truth (YAML Data + Jinja2 Templates) ]
                               │
                               ▼
        [ CI Pipeline: Pre-flight Verification (Batfish / Pytest) ]
                               │
                               ▼
        [ Orchestration Engine (Ansible / Python NAPALM / RESTCONF) ]
                               │
                               ▼
        [ Network Devices (Candidate Datastore -> Commit & Validate) ]
```

1. **Definisikan Source of Truth**: Strukturkan data operasional topologi ke dalam file YAML terpusat.
2. **Abstraksi Template**: Bangun template konfigurasi deklaratif menggunakan Jinja2.
3. **Uji Validasi Skema**: Gunakan skema JSON/YANG untuk memvalidasi variabel sebelum rendering.
4. **Eksekusi Transaksional**: Dorong konfigurasi ke perangkat target menggunakan interface terprogram (RESTCONF/NETCONF) ke dalam *candidate datastore*.
5. **Audit Differensial**: Tampilkan *diff* antara *running* dan *candidate*.
6. **Commit & Rollback Monitoring**: Eksekusi commit. Pantau telemetry. Jika telemetri abnormal terdeteksi dalam jendela waktu tertentu, jalankan rollback otomatis.

---

## 7. Analogy
Bayangkan memesan makanan di sebuah restoran:
- **CLI Scraping**: Anda masuk ke dapur, berteriak instruksi langkah-demi-langkah kepada koki: *"Ambil wajan, tuang minyak dua sendok, masukkan ayam, aduk 5 kali!"*. Jika koki mengganti merk wajan atau bergerak sedikit berbeda, instruksi Anda gagal atau makanan hangus. Di akhir, Anda harus melihat tumpukan piring kotor dan menebak apakah makanan sudah matang sempurna.
- **RESTCONF / NETCONF (Structured API)**: Anda duduk di meja makan, membaca Buku Menu standar (*YANG Model*). Menu mendefinisikan secara kaku apa yang bisa dipesan (tipe data, batasan). Anda mengisi formulir pesanan terstruktur (*JSON/XML Payload*) dan memberikannya ke pelayan (*API Endpoint*). Koki memproses seluruh pesanan secara atomik; jika satu bahan habis, seluruh transaksi dibatalkan (*Atomic Rollback*) tanpa membuat dapur berantakan. Anda menerima pesanan dalam wadah yang rapi dan terukur sesuai spesifikasi menu.

---

## 8. Diagram (ASCII)

### 8.1 NETCONF Datastore and Session State Engine
```
+-----------------------------------------------------------------------+
|                             Client Application                        |
|                     (Python ncclient / Ansible / CI/CD)               |
+-----------------------------------------------------------------------+
                                    │
                                    │  SSH Port 830 (Subsystem netconf)
                                    │  RPC: <edit-config>, <commit>
                                    ▼
+-----------------------------------------------------------------------+
| Network Operating System (NOS)                                        |
|                                                                       |
|  +--------------------+         <lock>         +--------------------+ |
|  |                    | ---------------------> |                    | |
|  | <running/>         |                        | <candidate/>       | |
|  | Active Data Plane  | <commit> / Rollback    | Scratchpad Store   | |
|  |                    | <--------------------- | (Staging Changes)  | |
|  +--------------------+                        +--------------------+ |
|            ▲                                              ▲           |
|            │                                              │           |
|            │ <copy-config>                                │           |
|  +--------------------+                                   │           |
|  | <startup/>         |                                   │           |
|  | NVRAM Persistence  |                                   │           |
|  +--------------------+                                   │           |
|                                                           │           |
|   Validation Engine (YANG RFC 7950 Constraints Validator) │           |
|   [ Schema Checks | Type Bounds | Reference Integrity Checks ]       |
+-----------------------------------------------------------------------+
```

### 8.2 End-to-End NetDevOps CI/CD Lifecycle
```
+---------------+     git push      +-----------------------------------------+
| Network Eng.  | ----------------> | Git Version Control (GitHub / GitLab)   |
+---------------+                   +-----------------------------------------+
                                                         │
                                                         │ Webhook Trigger
                                                         ▼
                                    +-----------------------------------------+
                                    | CI Runner: Syntax & Policy Linting       |
                                    | - yamllint, ansible-lint, pyang         |
                                    +-----------------------------------------+
                                                         │ Passed
                                                         ▼
                                    +-----------------------------------------+
                                    | Digital Twin Simulation (Batfish)       |
                                    | - Static Analysis: Routing Loop?        |
                                    | - Reachability & ACL Compliance Matrix  |
                                    +-----------------------------------------+
                                                         │ Passed
                                                         ▼
                                    +-----------------------------------------+
                                    | Deployment: Ansible / RESTCONF          |
                                    | - Candidate Datastore Load              |
                                    | - Confirmed Commit (Auto-rollback timer)|
                                    +-----------------------------------------+
                                                         │
                                                         ▼
                                    +-----------------------------------------+
                                    | Automated Validation (pyATS / pytest)   |
                                    | - BGP State == Established?             |
                                    | - Interface Packet Errors == 0?         |
                                    +-----------------------------------------+
                                           │                        │
                                    Success│                 Failure│ (Or Timeout)
                                           ▼                        ▼
                                    +-------------+          +----------------+
                                    | Final Commit|          | Rollback Event |
                                    +-------------+          +----------------+
```

---

## 9. Simple Example
Di bawah ini adalah perbandingan nyata mengambil status interface menggunakan pendekatan CLI Text Parsing vs RESTCONF Structured API.

### Pendekatan Scraping Tradisional (Fragile)
```python
import re

# Output mentah dari perintah CLI 'show ip interface brief'
raw_cli_output = """
Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0     192.168.1.1     YES NVRAM  up                    up      
GigabitEthernet0/1     unassigned      YES NVRAM  administratively down down    
"""

# Rentan rusak jika ada spasi tambahan atau perubahan nama kolom di OS baru
interfaces = {}
for line in raw_cli_output.strip().splitlines()[1:]:
    match = re.match(r"^(\S+)\s+(\S+)\s+\w+\s+\w+\s+(\S+)\s+(\S+)", line)
    if match:
        intf, ip, status, proto = match.groups()
        interfaces[intf] = {"ip": ip, "status": status, "protocol": proto}

print(interfaces)
```

### Pendekatan RESTCONF API Terstruktur (Robust & Model-Driven)
```python
import requests
import json

url = "https://192.168.1.254/restconf/data/ietf-interfaces:interfaces"
headers = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json"
}

response = requests.get(url, headers=headers, auth=('admin', 'C1sco123!'), verify=False)
data = response.json()

# Mengakses data secara deterministik tanpa regex
for intf in data["ietf-interfaces:interfaces"]["interface"]:
    name = intf["name"]
    enabled = intf["enabled"]
    print(f"Interface: {name}, Operational Enabled: {enabled}")
```

---

## 10. Practical Example (Konfigurasi Hands-On)

### 10.1 Jinja2 Templating & YAML Data Separation
File Data: `spine_data.yaml`
```yaml
---
hostname: spine-01
bgp_asn: 65001
router_id: 10.0.0.1
interfaces:
  - name: Loopback0
    description: RID_ROUTING_CONTROL
    ipv4: 10.0.0.1/32
  - name: Ethernet1/1
    description: P2P_LINK_TO_LEAF_01
    ipv4: 10.0.10.1/30
bgp_peers:
  - peer_ip: 10.0.10.2
    remote_asn: 65002
    description: LEAF-01
```

File Template: `cisco_bgp.j2`
```jinja2
hostname {{ hostname }}
!
interface {{ interfaces[0].name }}
 description {{ interfaces[0].description }}
 ip address {{ interfaces[0].ipv4 | ipaddr('address') }} {{ interfaces[0].ipv4 | ipaddr('netmask') }}
 no shutdown
!
{% for intf in interfaces[1:] %}
interface {{ intf.name }}
 description {{ intf.description }}
 ip address {{ intf.ipv4 | ipaddr('address') }} {{ intf.ipv4 | ipaddr('netmask') }}
 no shutdown
!
{% endfor %}
router bgp {{ bgp_asn }}
 bgp router-id {{ router_id }}
 bgp log-neighbor-changes
 {% for peer in bgp_peers %}
 neighbor {{ peer.peer_ip }} remote-as {{ peer.remote_asn }}
 neighbor {{ peer.peer_ip }} description {{ peer.description }}
 neighbor {{ peer.peer_ip }} update-source {{ interfaces[0].name }}
 {% endfor %}
```

### 10.2 Ansible Playbook Menggunakan Module Jaringan Deklaratif
File: `deploy_network.yml`
```yaml
---
- name: ORCHESTRATE LEAF SWITCH INFRASTRUCTURE
  hosts: leaves
  gather_facts: false
  connection: network_cli

  tasks:
    - name: Ensure Base VLAN Configuration is Compliant (Idempotent)
      cisco.ios.ios_vlans:
        config:
          - vlan_id: 100
            name: TENANT_APP
            state: active
          - vlan_id: 200
            name: TENANT_DB
            state: active
        state: merged

    - name: Configure Trunk Interfaces with Declarative Engine
      cisco.ios.ios_l2_interfaces:
        config:
          - name: GigabitEthernet0/2
            mode: trunk
            trunk:
              allowed_vlans: 100,200
              native_vlan: 1
        state: overridden

    - name: Push Model-Driven BGP Peering Configuration via RESTCONF
      ansible.builtin.uri:
        url: "https://{{ inventory_hostname }}/restconf/data/openconfig-network-instance:network-instances/network-instance=default/protocols"
        method: PATCH
        user: "{{ ansible_user }}"
        password: "{{ ansible_password }}"
        validate_certs: false
        headers:
          Content-Type: "application/yang-data+json"
          Accept: "application/yang-data+json"
        body_format: json
        body: >
          {
            "openconfig-network-instance:protocols": {
              "protocol": [
                {
                  "identifier": "BGP",
                  "name": "BGP_EXTERNAL",
                  "config": {
                    "identifier": "BGP",
                    "name": "BGP_EXTERNAL",
                    "enabled": true
                  }
                }
              ]
            }
          }
        status_code: [200, 204]
```

### 10.3 NETCONF Python Client Script (ncclient)
Skrip atomik memodifikasi antarmuka router menggunakan skema IETF berbasis NETCONF over SSH port 830:

```python
#!/usr/bin/env python3
import sys
from ncclient import manager
from ncclient.operations.rpc import RPCError

ROUTER_HOST = "192.168.10.10"
ROUTER_PORT = 830
USER = "netadmin"
PASS = "S3cur3N3tP@ss!"

# Payload XML didefinisikan menurut skema ietf-interfaces (RFC 7223)
config_payload = """
<config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>GigabitEthernet2</name>
      <description>UPLINK_TO_DATA_CORE</description>
      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">
        ianaift:ethernetCsmacd
      </type>
      <enabled>true</enabled>
      <ipv4 xmlns="urn:ietf:params:xml:ns:yang:ietf-ip">
        <address>
          <ip>172.16.254.1</ip>
          <netmask>255.255.255.252</netmask>
        </address>
      </ipv4>
    </interface>
  </interfaces>
</config>
"""

def main():
    try:
        with manager.connect(
            host=ROUTER_HOST,
            port=ROUTER_PORT,
            username=USER,
            password=PASS,
            hostkey_verify=False,
            device_params={'name': 'csr1000v'},
            timeout=30
        ) as m:
            print(f"[*] Terhubung ke {ROUTER_HOST}. Memeriksa lock pada datastore candidate...")
            
            # 1. Kunci Datastore Candidate untuk mencegah collision
            with m.locked(target='candidate'):
                print("[*] Datastore terkunci. Mengunggah konfigurasi delta...")
                
                # 2. Modifikasi konfigurasi pada candidate datastore
                m.edit_config(target='candidate', config=config_payload)
                
                # 3. Lakukan pengujian sintaks semantik
                print("[*] Menjalankan RPC <validate>...")
                m.validate(source='candidate')
                
                # 4. Confirmed Commit: Batalkan jika tidak dikonfirmasi permanen dalam 120 detik
                print("[*] Menerapkan <confirmed-commit> (timeout = 120s)...")
                m.commit(confirmed=True, timeout='120')
                
                # 5. Konfirmasi permanen jika pipeline mencapai tahap ini
                print("[*] Konfigurasi terverifikasi. Menerbitkan konfirmasi commit permanen...")
                m.commit()

            print("[+] Konfigurasi berhasil diterapkan secara atomik.")

    except RPCError as e:
        print(f"[!] NETCONF RPC Error: {e.info}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[!] Error Kritis Sistem: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## 11. Real World Example
Sebuah penyedia layanan cloud finansial mengelola fabric Datacenter Spine-and-Leaf yang terdiri atas 64 switch Arista EOS dan Cisco Nexus. Kebutuhan operasional menuntut provision VLAN baru dan *VRF route-target* untuk setiap instans nasabah baru dalam waktu kurang dari 5 menit tanpa downtime.

### Implementasi Solusi
1. Dibangun repositori Git bernama `fabric-tenants-repo`. Setiap kali insinyur membuka PR, mereka hanya menambahkan deklarasi blok data tenant YAML.
2. Pipeline GitHub Actions otomatis menjalankan:
   - **yamllint & schema check**: Memvalidasi format variabel.
   - **Batfish Analysis**: Model digital dari konfigurasi diekstraksi ke Batfish. Batfish memverifikasi apakah rute baru membocorkan tabel routing antar-tenant (*route leak analysis*) atau bertabrakan dengan segment ID yang sudah dialokasikan.
   - **Canary Rollout**: Konfigurasi pertama kali di-deploy via RESTCONF ke 2 switch Leaf di *staging pod*. Jika pengujian telemetry *health-check* (packet drops, route convergence time) lolos, pipeline melanjutkan deployment paralel ke seluruh fabric pod.
3. Dampak: Waktu provisioning terpangkas dari rata-rata 3 hari kerja menjadi 90 detik, dengan *zero human-induced configuration incidents* selama 14 bulan berturut-turut.

---

## 12. Trade-offs
Memilih arsitektur otomatisasi jaringan memerlukan evaluasi kompromi teknis:

- **Netmiko vs Structured API (RESTCONF/NETCONF)**:
  - *Netmiko*: Sangat kompatibel dengan 99% switch warisan (*legacy switches*) tanpa upgrade software. Namun, lambat (bergantung parsing spasi terminal dan latensi TTY), tidak memiliki integritas transaksi ACID, dan rapuh terhadap revisi banner/CLI.
  - *Structured API*: Memerlukan perangkat modern (Cisco IOS-XE, NX-OS, Arista EOS, Junos) dengan alokasi memori yang cukup untuk menjalankan daemon web/XML. Namun, menawarkan eksekusi instan, tipe data ketat, dan rollback transaksional native.
- **Agentless (Ansible) vs Programmatic Library (Python Direct)**:
  - *Ansible*: Kurva belajar rendah, ekosistem modul luas, deklaratif native. Namun, lambat dalam eksekusi berskala raksasa (*concurrency scaling*) karena overhead startup interpreter Python dan eksekusi task berantai.
  - *Direct Python (Asyncio / Scrapli / ncclient)*: Performa sangat tinggi (ribuan koneksi per detik), fleksibilitas penuh. Namun, membutuhkan penulisan boilerplate code yang intensif, pemeliharaan error handling mandiri, dan ketiadaan status manajemen deklaratif out-of-the-box.

---

## 13. When To Use
Gunakan arsitektur Network Automation & NetDevOps ketika:
- Mengelola lebih dari 20 node jaringan yang membutuhkan standardisasi konfigurasi berkala.
- Infrastruktur berbasis Spine-and-Leaf Underlay/Overlay (VXLAN EVPN) yang membutuhkan konsistensi replikasi konfigurasi identik di lusinan leaf node.
- Menjalankan lingkungan audit kepatuhan ketat (PCI-DSS, ISO 27001, SOC2), di mana setiap perubahan konfigurasi wajib memiliki jejak audit (*commit hash*, *approval sign-off*, *change diff*).
- Menghubungkan alur kerja provisioning aplikasi dengan provisioning infrastruktur jaringan secara dinamis via CI/CD.

---

## 14. When NOT To Use
Hindari atau batasi otomatisasi penuh ketika:
- **Insiden Out-of-Band Disaster Recovery**: Jaringan kehilangan konektivitas IP dasar (control plane terisolasi, interface gateway rontok). Pada kondisi ini, akses manual via Serial Console / Terminal Server adalah satu-satunya metode pemulihan yang realistis.
- **Investigasi Masalah Fisik Tingkat Rendah**: Kerusakan optik transreceiver, fluktuasi redaman kabel fiber (dB loss), atau kabel UTP yang longgar membutuhkan intervensi fisik teknisi lapangan daripada orkestrasi skrip.
- **Perangkat End-of-Life / Sumber Daya Terbatas**: Switch lawas dengan CPU MIPS 300MHz dan RAM 256MB akan mengalami *kernel panic* atau kelaparan resource jika dibebani daemon NETCONF/RESTCONF.

---

## 15. Common Mistakes
1. **Menganggap Otomasi Hanya Sebagai "Bash Scripting untuk CLI"**: Banyak insinyur memulai otomatisasi dengan sekadar membungkus ribuan baris perintah CLI prosedural ke dalam perulangan script `Netmiko` tanpa migrasi ke struktur data deklaratif atau API model-driven.
2. **Tidak Menggunakan Feature Candidate Datastore / Confirmed Commit**: Menjalankan skrip yang langsung menulis ke `running-config` pada perangkat produksi. Jika konektivitas SSH terputus di tengah transmisi baris perintah ACL/IP, perangkat akan terkunci permanen (*lockout*).
3. **Hardcoding Kredensial**: Menulis *plaintext username* dan *password* di dalam skrip Python atau playbook Ansible publik alih-alih menggunakan Ansible Vault, HashiCorp Vault, atau Environment Variables.
4. **Mengabaikan Idepontensi**: Menulis script yang terus menerus menambahkan baris konfigurasi (misal appending rule pada firewall/ACL) setiap kali skrip dijalankan, menyebabkan konsumsi memori tak terbatas dan penurunan performa lookup router.
5. **Absennya Pre-Validation Testing**: Mengirim konfigurasi langsung ke perangkat tanpa melewati linter atau pipeline simulasi seperti Batfish. Otomasi hanya mempercepat kerusakan jika kode konfigurasi yang didistribusikan mengandung *flaw* arsitektur.

---

## 16. Best Practices
1. **Source of Truth Tunggal**: Jangan izinkan modifikasi manual langsung pada perangkat produksi via CLI. Semua perubahan status harus berasal dari deklarasi Git repository (*Single Source of Truth*).
2. **Implementasikan Confirmed Commit**: Selalu gunakan mekanisme safety-net:
   ```python
   # Pola pengamanan commit NETCONF
   m.commit(confirmed=True, timeout='300')
   # Jalankan assertions verifikasi
   # Jika lolos:
   m.commit()
   ```
3. **Pemisahan Environment**: Bangun topologi staging menggunakan emulasi kontainer (misalnya *Containerlab* dengan image Arista cEOS atau Cisco XRv9000) untuk menguji skrip automasi sebelum eksekusi ke hardware fisik.
4. **Enkripsi Kredensial & Secrets**: Terapkan enkripsi end-to-end pada variabel lingkungan atau gunakan modul integrasi secret vault.
5. **Observabilitas Berbasis API**: Ganti syslog berbasis teks dan polling SNMP lawas dengan model *Streaming Telemetry* (gNMI/gRPC) berbasis skema model YANG untuk pemantauan performa real-time berlatensi ultra-rendah.

---

## 17. Troubleshooting
Panduan penanganan kegagalan eksekusi otomasi dan programabilitas:

### 17.1 Skenario: RESTCONF Mengembalikan HTTP 400 / 404 / 500
- **HTTP 404 Not Found**: Endpoint URI tidak cocok dengan modul YANG perangkat.
  - *Diagnosis*: Lakukan *query* ke discovery root: `GET https://<ip>/restconf/data/` untuk memvalidasi namespace YANG yang aktif di perangkat.
- **HTTP 400 Bad Request**: Payload JSON/XML melanggar batasan sintaks skema YANG (misalnya: interface MTU diisi string alih-alih unsigned integer).
  - *Diagnosis*: Gunakan tool `pyang -f tree <model.yang>` untuk memvalidasi struktur data dan tipe constraint yang diharapkan oleh perangkat.
- **HTTP 500 Internal Server Error**: Bug pada parser internal NOS saat mengompilasi model YANG ke database konfigurasi internal.
  - *Diagnosis*: Periksa log internal NOS (`show logging` di Cisco/Arista) untuk melihat crash trace pada process `restconfd` atau `confd`.

### 17.2 Skenario: NETCONF Sesi Mengalami Lock Timeout (Lock Denied)
- Gejala: RPC `<lock target="candidate"/>` mengembalikan pesan error: `resource-locked` oleh sesi lain.
- Tindakan Solusi:
  1. Identifikasi sesi yang memegang lock via RPC `<get-sessions>` atau CLI `show netconf-yang sessions`.
  2. Gunakan RPC `<kill-session>` dengan menyertakan `session-id` target pengunci untuk membebaskan antrean yang macet, atau konfigurasi idle-timeout pada daemon NETCONF perangkat.

### 17.3 Skenario: Netmiko Timeout Saat Eksekusi Perintah
- Gejala: Netmiko memunculkan `NetmikoTimeoutException: Timed-out reading welcome banner` atau `pattern not detected`.
- Tindakan Solusi:
  - Nonaktifkan paging CLI pada sesi secara eksplisit: `terminal length 0` atau `terminal width 512`.
  - Tingkatkan parameter `global_delay_factor` pada inisialisasi koneksi `ConnectHandler` untuk jaringan dengan latensi tinggi / satelit.
  - Periksa prompt termination character (misal router berada dalam konfigurasi config-if mode `(config-if)#`, sementara skrip hanya mengharapkan `#`).

---

## 18. Exercise
Selesaikan instruksi berikut secara mandiri:
1. Tulis sebuah skrip Python menggunakan pustaka `jinja2` yang menerima struktur data dictionary antarmuka Ethernet dan merender konfigurasi port-channel (LACP) lengkap dengan konfigurasi switchport trunk dan deskripsi antarmuka.
2. Buat playbook Ansible mandiri yang menggunakan modul `ansible.netcommon.cli_command` atau modul native OS pilihan Anda untuk mengekstrak versi operating system dari perangkat, kemudian mencatat informasi tersebut ke dalam format JSON lokal.
3. Gunakan `curl` untuk mengirimkan HTTP request ke endpoint RESTCONF pada router sandbox untuk mengambil seluruh data konfigurasi antarmuka dalam format representasi payload JSON.

---

## 19. Challenge
Rancang sebuah skrip Python modular menggunakan `ncclient` yang melakukan migrasi konfigurasi routing OSPF ke BGP secara aman pada perangkat berbasis Cisco IOS-XE:
- Skrip harus mengambil seluruh area OSPF yang berjalan via NETCONF menggunakan model IETF.
- Skrip harus menolak eksekusi jika router memiliki interface MTU tidak seragam di antarmuka trunk.
- Konfigurasi BGP baru harus dimasukkan ke datastore `candidate` bersamaan dengan penghapusan konfigurasi OSPF dalam **satu transaksi atomik tunggal** (*single RPC edit-config payload*).
- Manfaatkan fitur `confirmed-commit` berdurasi 60 detik. Skrip harus mengecek apakah BGP Neighbor status telah mencapai `Established` dalam kurun waktu 30 detik setelah commit sementara. Jika tidak, batalkan commit dan biarkan perangkat kembali ke konfigurasi OSPF sebelumnya secara otomatis.

---

## 20. Summary
- **Network Programmability** memodernisasi pengelolaan infrastruktur dari interaksi teks manual CLI menjadi manipulasi terstruktur berbasis data model (*YANG*) dan API (*NETCONF*, *RESTCONF*, *gNMI*).
- **Netmiko** dan **NAPALM** adalah fondasi otomatisasi Python: Netmiko menjembatani operasional CLI perangkat legacy, sementara NAPALM menyediakan abstraksi lintas platform deklaratif untuk konfigurasi dan status validasi.
- **Jinja2** dan **Ansible** memungkinkan pemisahan bersih antara logika arsitektur dan data inventaris, memastikan deployment konfigurasi berskala masif bersifat konsisten dan idempoten.
- **NETCONF** dan **RESTCONF** menyediakan manipulasi datastore yang aman dengan dukungan transaksi ACID, kemampuan roll-back native (*candidate store & confirmed commit*), dan keandalan validasi skema skematis.
- Metodologi **NetDevOps** menyatukan kontrol versi Git, pengujian simulasi digital twin (*Batfish*), validasi operasional otomatis (*pyATS*), dan deployment pipeline CI/CD, mengeliminasi kesalahan fatal manusia serta merealisasikan visi *Network as Code*.