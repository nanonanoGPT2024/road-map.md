# ADVANCED DETECTION ENGINEERING & ENTERPRISE CAPSTONE

---

### 1. IDENTITAS MODUL

* **Track:** Cyber Security
* **Kategori:** 07-Quality-and-Security
* **Bab:** 10 - Advanced Detection Engineering & Enterprise Capstone
* **Modul:** 01 (Module 10.1)
* **Tingkat Kesulitan:** Advanced / Lanjutan
* **Prasyarat:**
  * Pemahaman mendalam mengenai arsitektur internal OS (Windows Internals: Win32 API, Native API, PE format, Process Injection, ETW; Linux Internals: `/proc`, eBPF, Auditd, Syscalls).
  * Penguasaan MITRE ATT&CK Framework v14+, Cyber Kill Chain, dan piramida *Pyramid of Pain* (David Bianco).
  * Pemahaman scripting (Python 3.10+, PowerShell 5.1/7.x, Bash) serta Git/CI-CD automation pipelines.
  * Pengalaman operasional dengan arsitektur SIEM/XDR (Elasticsearch/OpenSearch, Splunk, Microsoft Sentinel) dan log telemetri enterprise (Sysmon, Windows Event Forwarding, Zeek, Auditd).
* **Estimasi Waktu Penyelesaian:** 16 Jam (8 Jam Teori & Analisis Arsitektur, 8 Jam Hands-on Lab & Capstone Execution).

---

### 2. LEARNING OBJECTIVES (LO)

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

* **LO-01:** Merancang arsitektur siklus hidup *Detection-as-Code* (DaC) berbasis GitOps dan CI/CD untuk otomatisasi validasi, linting, testing, dan deployment aturan deteksi secara modular ke multi-SIEM/EDR target.
* **LO-02:** Menulis, mengoptimalkan, dan mengompilasi aturan deteksi perilaku (*behavioral detection rules*) berbasis standar SigmaHQ untuk mendeteksi TTPs MITRE ATT&CK tanpa mengandalkan indikator statis (IOCs).
* **LO-03:** Merekayasa aturan YARA dan YARA-L untuk inspeksi memori proses (*volatile memory scanning*) dan artefak biner nhằm mendeteksi payload loader terinjeksi, shellcode staged/stageless, serta teknik *process tampering*.
* **LO-04:** Membangun *Threat Hunting Pipeline* berbasis hipotesis (*hypothesis-driven hunting*) yang mengolah telemetri mentah bervolume tinggi (*structured log pipelines*) menggunakan metrik anomali statistik dan analisis graf perilaku.
* **LO-05:** Mengoperasikan kerangka kerja *Adversary Emulation* terotomatisasi (Atomic Red Team) secara terukur untuk memverifikasi cakupan telemetri dan reliabilitas aturan deteksi pada target *endpoint*.
* **LO-06:** Mengorganisir dan mengeksekusi latihan *Purple Teaming* terstruktur guna mengukur efektivitas kontrol deteksi, mengidentifikasi *telemetry blind spots*, dan meminimalkan metrik *Mean Time to Detect* (MTTD).
* **LO-07:** Menganalisis dan memitigasi teknik *evasion* lawan tingkat lanjut, seperti manipulasi command-line, *process hollowing*, *direct system calls* (Syscalls evasion), dan penghentian telemetri ETW (*ETW patching*).
* **LO-08:** Menuntaskan skenario *Capstone Hybrid Enterprise Intrusion & Defense Exercise* dengan menahan penetrasi rantai serangan penuh (*full-chain attack*) dan mengonfigurasi mitigasi arsitektural berbasis MITRE D3FEND.

---

### 3. CONCEPT MAP & ARCHITECTURE DIAGRAM

Diagram berikut menggambarkan alur siklus hidup telemetri, kerangka kerja *Detection-as-Code*, dan interaksi *Purple Teaming* dalam sistem terintegrasi:

```text
+----------------------------------------------------------------------------------------------------+
|                                    DETECTION-AS-CODE (DaC) PIPELINE                                |
|                                                                                                    |
|  +-------------------+      +-------------------+      +-------------------+      +-------------+  |
|  |  Git Repository   | ---> | CI/CD Runner      | ---> | pySigma Compiler  | ---> | Production  |  |
|  |  (Sigma / YARA)   | Push | (Syntax Linting & | Test | (Target: Splunk,  | Deploy SIEM / XDR  |  |
|  |                   | / PR | Unit Testing)     |      | Elastic, Sentinel)|      | Datastores  |  |
|  +-------------------+      +-------------------+      +-------------------+      +------+------+  |
+------------------------------------------------------------------------------------------|---------+
                                                                                           |
                                      Query Synchronization & Scheduled Hunting Rules       |
                                                                                           v
+-----------------------------------------------------------------------------------+  +---+-------+
|                              ENTERPRISE RUNTIME ENVIRONMENT                       |  | Detection |
|                                                                                   |  | Engine /  |
|  +--------------------------+                      +---------------------------+  |  | Alerting  |
|  | Attacker / Emulation     |                      | Target Enterprise Host    |  |  | System    |
|  | (Atomic Red Team Engine) |                      | (Windows Server / Linux)  |  |  +-----+-----+
|  +------------+-------------+                      +-------------+-------------+  |        ^
|               |                                                  |                |        |
|               | Emulates TTPs                                    | Emits Events   |        | Ingests
|               v (e.g., T1003.001 comsvcs)                        v                |        | Normalized
|  +--------------------------+                      +---------------------------+  |        | Logs
|  | Target Process / API     | ===================> | Telemetry Sensors         |  |        |
|  | - LSASS Memory Access    | API Call Tracing     | - Windows Event Log / ETW |  |        |
|  | - Direct Syscall Invoked | Raw Memory Ingestion | - Sysmon (EID 1, 8, 10)   |  |        |
|  | - Cobalt Strike Injected |                      | - Linux Auditd / eBPF     |  |        |
|  +--------------------------+                      +-------------+-------------+  |        |
|                                                                  |                |        |
|                                                                  | Stream Events  |        |
|                                                                  v                |        |
|                                                    +---------------------------+  |        |
|                                                    | Log Shipping / Pipeline   +--+--------+
|                                                    | (Kafka / Logstash / Vector)  |
|                                                    +---------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

### 4. MENGAPA INI PENTING

Paradigma keamanan tradisional yang mengandalkan tanda tangan statis (*Indicator of Compromise* / IOC berbasis hash MD5/SHA256, domain, atau alamat IP) telah runtuh. Lawan modern menggunakan infrastruktur sekali pakai, enkripsi polimorfik, serta mengeksekusi kode langsung di memori (*in-memory execution*) melalui teknik *Living-off-the-Land Binaries and Scripts* (LOLBAS). Mengacu pada *Pyramid of Pain*, lapisan tertinggi dan paling sulit dihindari musuh adalah TTP (*Tactics, Techniques, and Procedures*).

Rekayasa deteksi tingkat lanjut (*Advanced Detection Engineering*) memandang deteksi sebagai produk rekayasa perangkat lunak, bukan sekadar penulisan kueri ad-hoc pada antarmuka pengguna SIEM. Tanpa pendekatan terstruktur:
1. **Alert Fatigue dan Kerapuhan Aturan:** Aturan deteksi yang tidak teruji memicu badai peringatan (*false positive storm*) atau gagal mendeteksi serangan saat terjadi variasi minor sintaks eksekusi lawan (*false negative*).
2. **Ketiadaan Validasi Berkelanjutan:** Tim keamanan berasumsi bahwa kontrol keamanannya berfungsi, padahal pembaruan sistem operasi atau modifikasi konfigurasi sensor kerap memutus pipa telemetri tanpa disadari (*telemetry blindness*).
3. **Dampak Finansial dan Operasional:** Waktu dwell time rata-rata musuh sebelum terdeteksi secara historis berkisar antara belasan hingga puluhan hari. Implementasi *Detection-as-Code* yang dipadukan dengan *Adversary Emulation* dan *Threat Hunting* memangkas *Mean Time to Detect* (MTTD) dan *Mean Time to Remediate* (MTTR) dari skala hari ke hitungan menit, mencegah eskalasi taktik dari akses awal (*Initial Access*) menjadi enkripsi massal (*Impact*).

---

### 5. APA ITU KONSEP (DEFINISI FORMAL MENDALAM)

#### A. Detection-as-Code (DaC)
*Detection-as-Code* adalah metodologi formal di mana logika deteksi didefinisikan, diverifikasi, diterapkan, dan dikelola menggunakan prinsip-prinsip siklus hidup pengembangan perangkat lunak modern (SDLC). Aturan ditulis dalam format deklaratif berbasis teks (seperti Sigma YAML), disimpan di bawah sistem kendali versi terdistribusi (Git), diuji secara otomatis melalui pipa CI/CD terhadap data telemetri sintesis, dan dikompilasi secara otomatis ke dalam bahasa kueri target SIEM/EDR (*native backends*).

#### B. Sigma dan YARA
* **Sigma:** Standar spesifikasi terbuka yang mendefinisikan aturan deteksi log terstruktur (*structured event log rules*) yang bersifat independen terhadap platform SIEM (*vendor-agnostic*). Sigma berfokus pada analisis atribut proses, jaringan, registri, dan berkas yang terekam pada log telemetri.
* **YARA:** Mesin pencocokan pola (*pattern matching engine*) yang dirancang khusus untuk mengidentifikasi dan mengklasifikasikan malware serta artefak biner pada sistem berkas atau ruang memori virtual (*process address space*) berdasarkan tanda tangan biner, string teks, ekspresi reguler (*regex*), dan heuristik modul internal (misalnya ekstensi PE atau ELF).

#### C. Threat Hunting Pipelines
Threat hunting berbasis hipotesis (*hypothesis-driven threat hunting*) adalah investigasi proaktif yang tidak dipicu oleh alert, melainkan diawali dengan merumuskan anggapan bahwa musuh telah berada di dalam jaringan menggunakan taktik tertentu. Pipa threat hunting memanfaatkan pemrosesan data besar (*big data log pipelines*) untuk mengekstraksi, memperkaya (*enrichment*), dan mengagregasi data telemetri guna mengekspos anomali statistik, deviasi garis dasar (*baseline deviations*), dan rantai eksekusi anomali (*abnormal process trees*).

#### D. Adversary Emulation & Purple Teaming
* **Adversary Emulation:** Praktik operasional peniruan tindakan, taktik, dan perkakas serangan musuh nyata yang telah didokumentasikan dalam basis intelijen ancaman (*Cyber Threat Intelligence* - CTI) menggunakan metode terstruktur dan terkontrol (misal: Atomic Red Team) untuk menguji batasan deteksi.
* **Purple Teaming:** Paradigma kolaboratif real-time terstruktur di mana operator penyerang (*Red Team*) dan analis pertahanan (*Blue Team*) bekerja secara sinkron. Red Team mengeksekusi teknik tertentu langkah demi langkah, sementara Blue Team secara instan memverifikasi keberadaan telemetri, efektivitas deteksi, dan melakukan penyetelan kueri deteksi saat itu juga.

---

### 6. BAGAIMANA CARA KERJANYA

#### A. Mekanika Pipa Detection-as-Code
1. **Authoring:** Detection Engineer menulis aturan Sigma (`rule.yml`) yang menargetkan sub-teknik MITRE ATT&CK tertentu (misal: T1059.001 - PowerShell Download Cradle).
2. **Static Analysis & Linting:** Saat dilakukan *Pull Request* ke branch `main`, CI/CD runner (misal: GitHub Actions) mengeksekusi linter untuk memverifikasi skema JSON/YAML, kepatuhan taksonomi atribut lapangan, dan metadata referensi MITRE.
3. **Compilation:** Menggunakan `pySigma` engine, aturan Sigma diterjemahkan secara otomatis menjadi kueri spesifik platform target, misalnya:
   * Target Elastic/OpenSearch: Lucene/KQL query.
   * Target Splunk: Splunk Processing Language (SPL).
   * Target Microsoft Sentinel: Kusto Query Language (KQL).
4. **Automated Testing:** CI/CD pipeline memuat log pengujian (*mock/golden telemetry files*) dan memvalidasi bahwa kueri yang dihasilkan memicu *True Positive* pada data serangan dan tidak menghasilkan *False Positive* pada data operasi normal.
5. **Deployment:** Pipeline memanfaatkan API SIEM/XDR untuk memperbarui atau menerbitkan aturan deteksi terjadwal (*Scheduled Analytic Rules*) secara atomik tanpa intervensi manual via UI.

```text
+--------------+      +-------------------+      +---------------------+      +----------------+
|  Sigma Rule  | ---> |   pySigma Engine  | ---> | Target AST / Token  | ---> | Native Query   |
| (YAML Source)|      | (Parsing & Normal)|      | (Platform Pipeline) |      | (SPL/KQL/EQL)  |
+--------------+      +-------------------+      +---------------------+      +----------------+
```

#### B. Mekanika Telemetri Tingkat Kernel
Pada sistem Windows, interaksi sistem tingkat rendah dipantau melalui Event Tracing for Windows (ETW). Komponen sensor (misal: Sysmon atau EDR driver `fltmgr.sys`) mengaitkan diri (*hooking*) pada kernel routine atau bertindak sebagai *ETW Consumer*. Saat eksekusi API seperti `CreateRemoteThread`, `VirtualAllocEx`, atau pembacaan memori via `OpenProcess` dengan hak akses `PROCESS_VM_READ` terjadi:
1. Kernel mengeksekusi instruksi dan memancarkan peristiwa ETW dari provider *Microsoft-Windows-Threat-Intelligence* atau *Microsoft-Windows-Kernel-Process*.
2. Driver EDR/Sysmon mencegat panggilan dan menghasilkan event log terstruktur (misal: Sysmon Event ID 10 untuk *ProcessAccess*, Event ID 1 untuk *ProcessCreation*).
3. Log dikirim melalui transport TLS oleh forwarder log (Winlogbeat/Splunk Forwarder) menuju klaster SIEM dalam milidetik untuk dicocokkan dengan kueri deteksi.

---

### 7. PERBANDINGAN PARADIGMA / TAKSONOMI MATRIKS

| Dimensi | Legacy SIEM Alerting | Detection-as-Code (DaC) | Hypothesis-Driven Threat Hunting | Automated Adversary Emulation |
| :--- | :--- | :--- | :--- | :--- |
| **Metode Operasi** | Konfigurasi manual melalui GUI konsol SIEM. | Berbasis repositori Git, pull requests, CI/CD pipelines. | Analisis eksploratif proaktif pada log bervolume tinggi. | Eksekusi otomatis payload dan sub-teknik MITRE terstandarisasi. |
| **Fokus Deteksi** | IOC Statis (IP, Hash, Domain) & Alert Out-of-the-Box. | TTP Berbasis Perilaku (*Behavioral/Heuristic*). | Anomali statistik, korelasi pola yang lolos dari filter alert. | Pengukuran ketahanan deteksi & identifikasi celah telemetri. |
| **Auditabilitas & Versioning**| Buruk; perubahan kueri langsung di produksi tanpa riwayat jelas. | Sempurna; setiap perubahan dilacak melalui Git commit, review, & log rilis. | Rendah; hipotesis dicatat manual dalam tiket atau playbook analitik. | Tinggi; seluruh *execution plan* tercatat dalam format terstruktur (YAML/JSON). |
| **Toleransi Evasion**| Nol; mudah dihindari hanya dengan mengubah hash malware atau domain. | Tinggi; menargetkan perilaku inti OS yang mutlak dibutuhkan malware. | Sangat Tinggi; analis mencari jejak anomali dari teknik stealth/evasion. | Sangat Tinggi; mengevaluasi keberhasilan deteksi pada ragam variasi payload. |
| **Biaya Pemeliharaan**| Tinggi akibat badai false positive (*alert fatigue*). | Terprediksi; false positive ditekan melalui unit testing pada pipa integrasi. | Variabel; bergantung pada keahlian senioritas analis ancaman. | Rendah; proses emulasi dapat dijadwalkan secara berulang otomatis. |

---

### 8. ANALISIS MENDALAM ATTACK SURFACE & VECTOR MATRIX

Matriks berikut menjabarkan vektor intrusi umum, jejak telemetri sistem operasi, tantangan false positive, dan mekanisme pengujian:

| Tactic & MITRE ID | Attack Vector / Execution Primitive | Host Telemetry Source | False Positive Baseline Triggers | Evasion Vectors & Bypasses | Emulation Mechanism (Atomic Red Team) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Execution**<br>`T1059.001` | PowerShell Download Cradle via System.Net.WebClient | Sysmon EID 1, Script Block Logging (EID 4104) | Skrip deployment software enterprise (SCCM, PDQ Deploy, Intune). | Obfuscation (Backticks, String Reversal, Variable Concatenation), Unmanaged PowerShell. | `T1059.001` Test 1: Download & Execute Script via WebClient. |
| **Credential Access**<br>`T1003.001` | Memory Dump LSASS via `MiniDumpWriteDump` / `comsvcs.dll` | Sysmon EID 10 (Target: `lsass.exe`), Sysmon EID 1 (`rundll32.exe`) | Antivirus agent, Windows Defender, EDR scanning agents, Hyper-V services. | Menggunakan snapshot handle (`PssCaptureSnapshot`), direct syscalls unhooked, API reflection. | `T1003.001` Test 2: LSASS dump using comsvcs.dll and rundll32. |
| **Defense Evasion**<br>`T1055.001` | Process Injection via `CreateRemoteThread` & `VirtualAllocEx` | Sysmon EID 8 (CreateRemoteThread), Sysmon EID 7 (ImageLoad) | Debugging tools (Visual Studio, Windbg), peranti performance profiler. | Early Bird APC Injection, Process Hollowing, Thread Hijacking, Module Stomping. | `T1055.001` Test 1: Process Injection via mavinject32.exe. |
| **Persistence**<br>`T1547.001` | Registry Run Keys / Startup Folder Modification | Sysmon EID 12/13 (Registry Event), EID 11 (File Create) | Pemasangan aplikasi sah oleh pengguna (OneDrive, Slack, Browser auto-launch). | Menggunakan registry subkey tersembunyi (*null character embedded*), direct registry hive modification. | `T1547.001` Test 1: Reg Key Run / RunOnce modification. |
| **Lateral Movement**<br>`T1021.002` | SMB/Windows Admin Shares via PsExec primitive | Security EID 4624 (Type 3), EID 5145, Sysmon EID 1 (Service execution) | Distribusi patch jaringan lokal, vulnerability scanning terjadwal (Nessus/Qualys). | Penggunaan port redirection lokal, WMI lateral movement (`Win32_ProcessCreate`). | `T1021.002` Test 1: Execute command via SMB named pipes. |

---

### 9. CODE EXAMPLE SEDERHANA

Contoh dasar aturan Sigma untuk mendeteksi eksekusi utilitas dump memori proses via `rundll32.exe` dan pemanggilan `comsvcs.dll` (MITRE ATT&CK `T1003.001`):

```yaml
title: LSASS Memory Dump via Rundll32 and Comsvcs.dll
id: 3f8b0304-6294-46b7-a36c-2f22b0c34511
status: production
description: Mendeteksi penggunaan utilitas bawaan Windows rundll32.exe yang memanggil library comsvcs.dll untuk melakukan dumping memori proses LSASS.
references:
    - https://attack.mitre.org/techniques/T1003/001/
author: Cyber Security Architect
date: 2026-03-30
tags:
    - attack.credential_access
    - attack.t1003.001
logsource:
    category: process_creation
    product: windows
detection:
    selection_img:
        Image|endswith: '\rundll32.exe'
        OriginalFileName: 'RUNDLL32.EXE'
    selection_cli:
        CommandLine|contains|all:
            - 'comsvcs'
            - 'MiniDump'
    condition: selection_img and selection_cli
fields:
    - ComputerName
    - User
    - CommandLine
    - ParentCommandLine
falsepositives:
    - Aksi debugging internal oleh software administrator yang sangat jarang terjadi.
level: high
```

Hasil kompilasi native Splunk Processing Language (SPL) yang dihasilkan oleh `sigma-cli`:

```text
(Image="*\\rundll32.exe" OR OriginalFileName="RUNDLL32.EXE") AND (CommandLine="*comsvcs*" AND CommandLine="*MiniDump*")
```

---

### 10. CODE EXAMPLE LANJUTAN

Berikut implementasi production-ready yang mencakup skrip CI/CD validator, aturan Sigma dengan pengkondisian regex toleran-evasion, dan aturan YARA untuk pemindaian memori PE injected.

#### A. Production-Ready Sigma Rule dengan Regular Expression Anti-Evasion
Menangani variasi penulisan path, ekstra spasi, case sensitivity, serta pemanggilan fungsi ordinal:

```yaml
title: Advanced Suspicious Rundll32 Execution comsvcs Export
id: b8d52361-9c84-48f8-b3bc-d0b89218d6a8
status: production
description: |
    Mendeteksi pemanggilan fungsi ekspor MiniDump pada comsvcs.dll baik menggunakan nama string 
    maupun pemanggilan ordinal (#24) dengan normalisasi CommandLine dan regex pattern.
references:
    - https://attack.mitre.org/techniques/T1003/001/
author: Detection Engineering Enterprise Team
date: 2026-03-30
tags:
    - attack.credential_access
    - attack.t1003.001
logsource:
    category: process_creation
    product: windows
detection:
    process_selection:
        - Image|endswith: '\rundll32.exe'
        - OriginalFileName: 'RUNDLL32.EXE'
    command_selection:
        CommandLine|re: '(?i)(?:comsvcs(?:\.dll)?\s*(?:,|\s)\s*(?:#24|MiniDumpW?)|MiniDumpW?\s+.*lsass)'
    condition: process_selection and command_selection
fields:
    - ProcessId
    - Image
    - CommandLine
    - ParentProcessId
    - ParentImage
falsepositives:
    - Prosedur crash-reporting internal enterprise yang terotorisasi secara spesifik.
level: critical
```

#### B. Aturan YARA untuk Scanning In-Memory Process Injection (Reflective DLL / Shellcode)
Mendeteksi artefak injeksi Cobalt Strike / Metasploit stager di dalam alokasi memori RWX:

```yara
rule Suspicious_Injected_Reflective_Loader {
    meta:
        description = "Mendeteksi keberadaan pola bootstrap memory injection dan reflective PE loader di virtual memory"
        author = "Enterprise Threat Detection"
        threat_level = "Critical"
        mitre_att = "T1055.001, T1055.002"
        date = "2026-03-30"
    strings:
        // Pola x86/x64 generic stub pemanggilan kernel32/ntdll resolution
        // cld; and rsp, ... ; call ...
        $stub_x64 = { FC 48 83 E4 F0 E8 [4] 41 51 41 50 52 51 56 }
        // API Hashing (ROR13 Hash strings umum: LoadLibraryA, VirtualAlloc)
        $ror13_hash = { 8B 4D 3C 8B 44 0D 78 01 CD 8B 79 20 01 CF }
        // Indikasi MZ header dalam dynamic memory allocation
        $mz_header = { 4D 5A }
        // String umum reflective injection
        $str_kernel32 = "KERNEL32.DLL" fullword nocase
        $str_ntdll = "NTDLL.DLL" fullword nocase
    condition:
        // Memastikan eksekusi hanya diterapkan pada Virtual Address ranges (Memory Scan)
        $mz_header at 0 and ($stub_x64 or $ror13_hash) and ($str_kernel32 or $str_ntdll)
}
```

#### C. Automated CI/CD Engine Validator & Converter (Python Script)
Skrip otomatis yang berjalan di GitHub Actions untuk memvalidasi sintaks seluruh aturan Sigma, memastikan penandaan MITRE benar, menguji terhadap *mock telemetry*, dan mengompilasi ke format Elasticsearch EQL:

```python
#!/usr/bin/env python3
"""
Enterprise Detection-as-Code Pipeline Automation Engine
Validates Sigma syntax, ensures MITRE ATT&CK schema compliance,
and builds compiled EQL/SPL output packages.
"""

import sys
import os
import yaml
from pathlib import Path
from sigma.collection import SigmaCollection
from sigma.backends.elasticsearch import LuceneBackend
from sigma.pipelines.elasticsearch import ecs_windows

def validate_mitre_tags(tags: list) -> bool:
    """Memvalidasi keberadaan dan format tag MITRE ATT&CK."""
    has_technique = False
    for tag in tags:
        if tag.startswith("attack.t"):
            has_technique = True
            break
    return has_technique

def run_pipeline(rules_dir: Path, output_file: Path) -> int:
    print(f"[*] Starting Validation on Directory: {rules_dir}")
    backend = LuceneBackend(ecs_windows())
    compiled_queries = []
    error_count = 0

    for rule_path in rules_dir.rglob("*.yml"):
        try:
            with open(rule_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
            
            # 1. Validasi Schema Metadata
            required_keys = {"title", "id", "status", "logsource", "detection", "tags"}
            if not required_keys.issubset(content.keys()):
                print(f"[!] Schema Error in {rule_path}: Missing mandatory keys")
                error_count += 1
                continue

            # 2. Validasi Kepatuhan MITRE ATT&CK Tagging
            if not validate_mitre_tags(content.get("tags", [])):
                print(f"[!] Compliance Error in {rule_path}: Missing explicit attack.tXXXX tag")
                error_count += 1
                continue

            # 3. Kompilasi Rule Menggunakan pySigma Backend
            with open(rule_path, "r", encoding="utf-8") as f:
                sigma_rule = SigmaCollection.from_yaml(f.read())
            
            query = backend.convert(sigma_rule)
            compiled_queries.append({
                "id": content["id"],
                "title": content["title"],
                "compiled_query": query
            })
            print(f"[+] Successfully validated & compiled: {content['title']}")

        except Exception as e:
            print(f"[!] Parsing/Compilation Failure in {rule_path}: {str(e)}")
            error_count += 1

    if error_count > 0:
        print(f"[-] Pipeline Failed with {error_count} error(s).")
        return 1

    # Simpan output kueri jika validasi 100% lolos
    with open(output_file, "w", encoding="utf-8") as out:
        yaml.dump(compiled_queries, out)
    
    print(f"[SUCCESS] All rules passed validation. Artifacts saved to {output_file}")
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python validator.py <rules_directory> <output_manifest.yml>")
        sys.exit(1)
    sys.exit(run_pipeline(Path(sys.argv[1]), Path(sys.argv[2])))
```

---

### 11. DIAGRAM ALUR SERANGAN & MITIGASI

Diagram sequence berikut memvisualisasikan eksekusi TTP oleh Red Team, intervensi telemetri kernel, komparasi kueri deteksi, dan aksi blokir otomatis:

```text
[RED TEAM / ATOM]          [TARGET OS KERNEL]          [SYSMON / SENSOR]         [LOG PIPELINE / SIEM]       [SOAR / DEFENDER]
        |                          |                           |                           |                         |
        | 1. Invoke MiniDumpW      |                           |                           |                         |
        |    via Rundll32 comsvcs  |                           |                           |                         |
        |------------------------->|                           |                           |                         |
        |                          | 2. Process Creation       |                           |                         |
        |                          |    Syscall: NtCreateUser  |                           |                         |
        |                          |-------------------------->|                           |                         |
        |                          |                           | 3. Emit Sysmon EID 1      |                         |
        |                          |                           |    (CmdLine, Hashes, Parent)                      |
        |                          |                           |-------------------------->|                         |
        |                          | 4. Handle to LSASS opened |                           |                         |
        |                          |    DesiredAccess: 0x1FFFFF|                           |                         |
        |                          |-------------------------->|                           |                         |
        |                          |                           | 5. Emit Sysmon EID 10     |                         |
        |                          |                           |    (Target: lsass.exe)    |                         |
        |                          |                           |-------------------------->|                         |
        |                          |                           |                           | 6. Match DaC Rule:      |
        |                          |                           |                           |    b8d52361-9c84-...    |
        |                          |                           |                           |    Score: Critical      |
        |                          |                           |                           |------------------------>|
        |                          |                           |                           |                         | 7. Trigger SOAR Playbook:
        |                          |                           |                           |                         |    - Terminate Rundll32 PID
        |                          |                           |                           |                         |    - Isolate Host (EDR API)
        |                          |                           |                           |                         |    - Revoke Session Tokens
        |                          |                           |                           |<------------------------|
        |                          |<--------------------------------------------------------------------------------|
        |                          | 8. SIGKILL PID / Sever Connection                     |                         |
        | x Execution Blocked      |                                                       |                         |
```

---

### 12. TRADE-OFFS & SECURITY VS USABILITY / PERFORMANCE

#### A. Kompleksitas Regex vs Utilisasi CPU Pipeline Ingest
* **Pertimbangan:** Pemrosesan ekspresi reguler (*Regular Expressions*) non-linear atau evaluasi kondisi string bervolume tinggi di pipeline log forwarder (seperti Logstash/Vector) meningkatkan beban CPU secara eksponensial.
* **Trade-off:** Penggunaan pencocokan string sederhana (`contains`) jauh lebih efisien pada kapasitas ingestion SIEM (ratusan ribu peristiwa per detik), tetapi mudah diakali dengan teknik manipulasi spasi dan kutip. Sebaliknya, regex kompleks berbasis token aman dari bypass variasi sintaks, tetapi mengonsumsi komputasi tinggi dan berisiko memicu DoS pada pipeline stream-processing.

#### B. Tingkat Sensitivitas Deteksi vs Kelelahan Peringatan (*Alert Fatigue*)
* **Pertimbangan:** Deteksi yang mencakup pemanggilan API secara luas (misalnya pemantauan *Sysmon Event ID 10* untuk semua pembukaan handle ke `lsass.exe`) memberikan visibilitas mutlak.
* **Trade-off:** Mengaudit pembukaan handle proses menghasilkan volume telemetri masif dan rentan terhadap false positive yang dipicu oleh perangkat lunak enterprise sah (antivirus, software agent, manajemen aset). Pemfilteran ketat menekan volume log dan menghemat biaya konsumsi SIEM, namun berisiko memunculkan celah buta (*telemetry blind spot*) yang dapat dimanfaatkan lawan untuk melancarkan serangan berbasis unhooking atau memory read bertingkat.

---

### 13. EDGE CASES & COMPLEX FAILURE MODES

1. **Manipulasi Event Tracing for Windows (ETW Patching):**
   * *Mekanika Kegagalan:* Penyerang dengan hak eksekusi *unmanaged code* dapat membuka modul `ntdll.dll` pada ruang memorinya sendiri dan menimpa instruksi fungsi `EtwEventWrite` dengan opcode instruksi `RET` (`0xC3`).
   * *Dampak:* EDR atau sensor berbasis ETW pengguna (*user-mode ETW hook*) tidak lagi menerima sinyal kejadian proses secara total, mengakibatkan deteksi berbasis sub-sistem ETW gagal memicu alert meski payload beroperasi penuh.
2. **Keterbatasan Ukuran Command-Line dan Process Masquerading:**
   * *Mekanika Kegagalan:* Deteksi berbasis string `CommandLine` pada Windows Event ID 1/Sysmon dapat dilewati jika musuh menginjeksikan parameter palsu ke Process Environment Block (PEB) saat proses diinisiasi dalam keadaan *suspended*, lalu menulis ulang pointer PEB ke argumen asli setelah registrasi proses selesai.
   * *Dampak:* Log proses mencatat parameter palsu yang tidak berbahaya (*benign decoy parameters*), menyamarkan eksekusi instruksi destruktif dari kueri berbasis string parsing.
3. **Log Truncation and Log Pipeline Backpressure:**
   * *Mekanika Kegagalan:* Lonjakan volume log yang masif atau batasan buffer maksimum pada pengirim log (seperti batas 64KB pada Windows Event Log payloads) memotong *Script Block Logging* (EID 4104) panjang.
   * *Dampak:* Fragmen kode berbahaya yang berada di akhir script payload terpotong dan luput dari evaluasi kueri regex deteksi SIEM.

---

### 14. ANTI-PATTERNS & COMMON VULNERABILITIES

* **Anti-Pattern 1: Deteksi Berbasis Nama File Eksekusi Saja.**
  * *Pola Rentan:* `Image|endswith: '\mimikatz.exe'`
  * *Analisis Celah:* Musuh hanya perlu mengubah nama file binary menjadi `calc.exe` atau `svchost.exe` untuk melewati deteksi. Deteksi wajib memvalidasi `OriginalFileName` dari metadata PE Header, hash integritas kode biner, atau tingkah laku proses.
* **Anti-Pattern 2: Menggunakan Pengecualian Global Berbasis Jalur Direktori (*Path Exclusions*).**
  * *Pola Rentan:* Pengecualian path `CommandLine|contains: 'C:\Program Files\EnterpriseApp\'` untuk menghilangkan false positive.
  * *Analisis Celah:* Penyerang dapat menyusupkan dan mengeksekusi malware langsung dari sub-direktori folder tersebut untuk mengeksploitasi kelonggaran aturan deteksi.
* **Anti-Pattern 3: Drift Konfigurasi Produksi (*Manual GUI Drift*).**
  * *Pola Rentan:* Detection Engineer menyunting aturan langsung pada Web UI SIEM produksi untuk mematikan peringatan tanpa menyelaraskan perubahan ke repositori Git.
  * *Analisis Celah:* Hilangnya jejak audit (*audit trail*), hilangnya modifikasi saat pipeline deployment otomatis dieksekusi berikutnya, serta rentan merusak konsistensi logika deteksi tanpa peer review.

---

### 15. BEST PRACTICES & ENTERPRISE REMEDIATION GUIDE

1. **Implementasi Siklus Hidup Pipa GitOps untuk Deteksi:**
   * Seluruh modifikasi kueri, ambang batas waktu (*time window*), dan kriteria pemfilteran harus berupa file konfigurasi di repositori Git.
   * Terapkan kebijakan *mandatory branch protection*: Setiap aturan baru atau perubahan wajib melalui *Pull Request* (PR) dengan validasi lulus CI linter dan disetujui minimal oleh dua analis (*Four-Eyes Principle*).
2. **Standardisasi Pemetaan Taksonomi MITRE D3FEND:**
   * Jangan hanya memetakan teknik serangan (ATT&CK); hubungkan setiap aturan deteksi ke teknik mitigasi defensif D3FEND yang relevan, seperti:
     * `d3f:ProcessSpawnAnalysis` untuk deteksi anomali pohon proses.
     * `d3f:FileModificationAnalysis` untuk pemantauan integritas artefak sistem.
     * `d3f:SystemCallAnalysis` untuk audit kernel hooking dan direct syscalls.
3. **Verifikasi Kontinu Berbasis Adversary Emulation:**
   * Jadwalkan eksekusi berkala uji keamanan otomatis menggunakan Atomic Red Team terhadap mesin *canary* di lingkungan produksi dan staging.
   * Jika eksekusi atomik gagal memicu alert di SIEM dalam rentang waktu toleransi (misal 5 menit), pipeline monitoring harus otomatis mencatat status degradasi kontrol keamanan (*Detection Drift Alert*).

---

### 16. HANDS-ON LAB STEP-BY-STEP

#### Skenario Lab
Membangun siklus penuh deteksi T1003.001: Menulis aturan Sigma, memvalidasi dengan CI test harness, mengeksekusi Adversary Emulation via Atomic Red Team, memverifikasi tangkapan telemetri Sysmon, dan mengotomatisasi pengetesan pipeline.

#### Kebutuhan Lingkungan:
* 1x Windows Server (Host Target dengan Sysmon terinstal dan terkonfigurasi).
* 1x Linux Host (Detection Engineering CI/CD workstation dengan Python 3.10+).

#### Langkah 1: Persiapan Environment Workstation (Linux Engine)
Instal dependensi tools validasi Sigma:
```bash
sudo apt-get update && sudo apt-get install -y python3-pip git
pip3 install sigma-cli pySigma pySigma-backend-elasticsearch pySigma-pipeline-sysmon
mkdir -p enterprise-detection-repo/rules
cd enterprise-detection-repo
```

#### Langkah 2: Pembuatan Aturan Sigma Khusus
Simpan file berikut ke `rules/proc_creation_win_susp_comsvcs_dump.yml`:
```yaml
title: Potential In-Memory LSASS Dump via Comsvcs DLL
id: a87612f0-1e5b-4890-951c-4395bcde2190
status: experimental
description: Mendeteksi penulisan memori proses comsvcs.dll dump yang mengindikasikan ekstraksi kredensial.
author: BlueTeam Specialist
date: 2026-03-30
tags:
    - attack.credential_access
    - attack.t1003.001
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith: '\rundll32.exe'
        CommandLine|contains: 'comsvcs'
        CommandLine|re: '(?i)(?:#24|MiniDump)'
    condition: selection
fields:
    - CommandLine
    - ParentImage
level: high
```

#### Langkah 3: Validasi Sintaks dan Kompilasi Query
Jalankan kompilasi menggunakan `sigma-cli` untuk memvalidasi tidak adanya kesalahan parsing:
```bash
# Validasi sintaks rule
sigma check rules/proc_creation_win_susp_comsvcs_dump.yml

# Kompilasi ke backend Elastic Query Language (EQL)
sigma convert -t elasticsearch -p sysmon rules/proc_creation_win_susp_comsvcs_dump.yml
```
*Output yang Diharapkan:* Query EQL valid yang siap dijalankan di SIEM.

#### Langkah 4: Adversary Emulation pada Windows Target Host
Buka terminal Administrator PowerShell di host target dan jalankan pengujian atomik ATT&CK T1003.001:
```powershell
# Instal modul Invoke-AtomicRedTeam jika belum terpasang
IEX (IWR 'https://raw.githubusercontent.com/redcanaryco/invoke-atomicredteam/master/install-atomicredteam.ps1' -UseBasicParsing);
Install-AtomicTechnique -Technique T1003.001 -Force

# Eksekusi payload atomik spesifik comsvcs
Invoke-AtomicTest T1003.001 -TestNumbers 2
```

#### Langkah 5: Verifikasi Telemetri Log Lokal (Sysmon)
Verifikasi apakah Sysmon menangkap eksekusi proses tersebut pada Windows Event Log:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Sysmon/Operational'; Id=1} -MaxEvents 5 | 
Where-Object { $_.Message -match "rundll32.exe" -and $_.Message -match "comsvcs" } | 
Format-List TimeCreated, Message
```
*Hasil Verifikasi:* Harus muncul entri log Sysmon Event ID 1 yang merekam atribut eksekusi lengkap beserta argumen `MiniDump` dan target LSASS Process ID.

#### Langkah 6: Pembersihan Sisa Emulasi (*Lab Cleanup*)
Hapus file artefak dump yang terbentuk di lingkungan lab:
```powershell
Invoke-AtomicTest T1003.001 -TestNumbers 2 -Cleanup
Remove-Item -Path "$env:TEMP\*.dmp" -ErrorAction SilentlyContinue
```

---

### 17. REAL-WORLD CASE STUDY & INCIDENT ANALYSIS ENTERPRISE

#### Latar Belakang Insiden
Sebuah institusi perbankan multinasional mengalami intrusi yang diidentifikasi terafiliasi dengan aktor ancaman persisten tingkat lanjut (*Advanced Persistent Threat* - APT). Sasaran utama penyerang adalah menjangkau server pemrosesan transaksi inti (*core banking payment engine*).

#### Vektor Masuk dan Rantai Serangan (*Attack Chain*)
1. **Initial Access:** Kredensial VPN dikompromikan melalui serangan peniruan identitas (*Session Token Hijacking*).
2. **Discovery & Lateral Movement:** Lawan menyusup antar-segmen jaringan menggunakan WMI query dan autentikasi Kerberos Ticket over Pass-the-Hash.
3. **Execution & Evasion:** Penyerang mendarat pada jump host administrator dan mengeksekusi *Living-off-the-Land*:
   * Menggunakan binary sah `rundll32.exe` yang memanggil fungsi ekspor `#24` dari `C:\Windows\System32\comsvcs.dll` untuk mendump memori proses `lsass.exe` langsung ke direktori sementara sistem.
   * Parameter dieksekusi dengan variasi pemisahan argumentasi non-standar:
     `rundll32.exe  comsvcs.dll,#24 [LSASS_PID] C:\Windows\Temp\debug.tmp full`
4. **Failure of Legacy SIEM:** Mesin SIEM berbasis korelasi lama milik perbankan gagal memicu alarm karena kueri deteksinya dikonfigurasi menggunakan string literal statis `CommandLine contains "MiniDump"` dan `CommandLine contains "lsass.dmp"`. Kueri ini sepenuhnya dilewati oleh pemanggilan fungsi via ordinal `#24` dan ekstensi berkas acak `.tmp`.

#### Analisis Forensik dan Mitigasi Detection Engineering
1. **Analisis Telemetri Sysmon Host:**
   Tim respons insiden mengekstraksi Sysmon EID 10 (*ProcessAccess*) yang menunjukkan proses `rundll32.exe` meminta hak akses `0x1FFFFF` terhadap `TargetImage: C:\Windows\System32\lsass.exe`. Ditemukan pula Sysmon EID 1 (*ProcessCreation*) yang menunjukkan *ParentImage* berasal dari skrip remote orchestration tak terotorisasi.
2. **Remediasi Detection-as-Code Terpasang:**
   Aturan deteksi darurat dirumuskan menggunakan regex non-anchored yang memvalidasi pola ordinal ekspor library Windows:
   `CommandLine|re: 'comsvcs(?:\.dll)?(?:\s*,\s*|\s+)#24'`
   Aturan ini dipasangkan dengan deteksi korelasi Sysmon EID 10: memicu alert kritis setiap kali ada binary dari direktori `system32` selain modul sistem Windows terdaftar yang meminta hak akses pembacaan memori penuh (`PROCESS_ALL_ACCESS` atau `PROCESS_VM_READ`) ke proses `lsass.exe`.
3. **Hasil Perbaikan Arsitektur:**
   Waktu MTTD dipangkas dari rata-rata historis 72 jam menjadi 4 detik setelah aturan DaC diterapkan di pipeline terdistribusi, sekaligus menutup celah bypass pemanggilan berbasis ordinal secara permanen di seluruh enterprise.

---

### 18. QUIZ PEMAHAMAN & CHALLENGE

#### Pertanyaan Evaluasi

1. Mengapa mendeteksi eksekusi utilitas dumping memori menggunakan aturan berbasis atribut `OriginalFileName` lebih tangguh (*resilient*) dibandingkan mendeteksi berbasis nama file eksekusi pada `Image`?
   * A. Karena `OriginalFileName` dialokasikan secara dinamis oleh kernel saat proses berjalan.
   * B. Karena `OriginalFileName` diekstraksi dari blok resource PE header internal biner sehingga tidak berubah meskipun penyerang mengubah nama berkas `.exe`.
   * C. Karena `OriginalFileName` hanya dapat dimodifikasi oleh pengguna dengan hak akses Administrator.
   * D. Karena file sistem NTFS menolak eksekusi file jika `OriginalFileName` tidak cocok dengan nama file lokal.

2. Seorang Detection Engineer mengamati bahwa aturan deteksi PowerShell miliknya dilewati oleh musuh yang menggunakan teknik penyamaran spasi ganda, kutip tunggal bersarang, dan variabel acak. Langkah rekayasa deteksi mana yang paling tepat untuk memitigasi teknik penghindaran tersebut?
   * A. Menghentikan proses PowerShell secara global di seluruh enterprise.
   * B. Beralih ke pencocokan hash SHA-256 binary `powershell.exe`.
   * C. Mengimplementasikan inspeksi log berbasis *PowerShell Script Block Logging* (Event ID 4104) yang secara otomatis melakukan de-obfuskasi kode sebelum diuraikan oleh engine eksekusi OS.
   * D. Menambahkan lebih banyak string statis ke dalam klausa kueri teks SIEM.

3. Apa keunggulan teknis mendasar dari arsitektur *Detection-as-Code* (DaC) dibandingkan manajemen aturan deteksi tradisional berbasis Web-UI SIEM?
   * A. DaC mengurangi konsumsi telemetri jaringan pada sensor endpoint.
   * B. DaC memungkinkan pengujian otomatis validasi sintaks, uji regresi berbasis telemetri rekaman, dan pelacakan versi perubahan kueri menggunakan Git secara terkontrol.
   * C. DaC menghilangkan sepenuhnya kebutuhan sensor log agent pada sistem operasi endpoint.
   * D. DaC mengotomatisasi penulisan eksploitasi oleh tim Red Team tanpa konfigurasi.

4. Dalam analisis performa kueri deteksi SIEM, skenario mana yang berpotensi paling besar menyebabkan fenomena *Catastrophic Backtracking* dan menghabiskan sumber daya komputasi pipeline stream-processing?
   * A. Kueri pencocokan awalan sederhana: `Image|startswith: 'C:\Windows\'`.
   * B. Regex yang mengandung pola pengulangan bertingkat tidak terbatas (*nested greedy quantifiers*) seperti `CommandLine|re: '.*(a+)+.*'`.
   * C. Pengujian keberadaan nilai field: `TargetObject|endswith: '\CurrentVersion\Run'`.
   * D. Evaluasi kesetaraan bilangan bulat biner (*integer bitmask match*).

5. Pada framework *Pyramid of Pain*, lapisan pertahanan manakah yang dipengaruhi secara langsung oleh pengujian adversary emulation berbasis Atomic Red Team yang berfokus pada eksekusi sub-teknik MITRE ATT&CK?
   * A. Hash Values.
   * B. IP Addresses.
   * C. TTPs (Tactics, Techniques, and Procedures).
   * D. Domain Names.

---

#### Kunci Jawaban & Rasionalisasi
1. **Jawaban: B.** Nilai `OriginalFileName` tertanam secara statis di dalam metadata PE header (*Version Information Structure*) saat binary dikompilasi oleh pengembang aslinya. Mengubah nama file fisik di disk tidak mengubah resource header internal ini tanpa proses kompilasi ulang total.
2. **Jawaban: C.** PowerShell Script Block Logging (EID 4104) menangkap konten eksekusi aktual saat runtime tepat sebelum interpreter mengeksekusi instruksi. Ini berarti kode yang diobfuskasi bertingkat telah didekodekan (*unpacked*) ke bentuk teks instruksi aslinya oleh runtime PowerShell, menjadikannya lapisan telemetri paling efektif melawan obfuskasi.
3. **Jawaban: B.** DaC memadukan prinsip rekayasa perangkat lunak modern ke dalam operasi deteksi: pengujian regresi berkelanjutan, linting sintaks, modularitas penulisan, peer-review terintegrasi, dan pencegahan drift konfigurasi melalui deployment terotomatisasi.
4. **Jawaban: B.** Pola regular expression dengan nested quantifiers non-deterministik memicu engine regex tipe NFA (*Nondeterministic Finite Automaton*) melakukan evaluasi branch secara eksponensial ketika menemukan input yang tidak cocok (*mismatching string*), berujung pada konsumsi CPU 100% dan pembekuan proses ingest.
5. **Jawaban: C.** Atomic Red Team secara khusus dibangun untuk memvalidasi dan menguji TTPs, yang merepresentasikan cara kerja, metodologi, dan prosedur taktis musuh—posisi puncak dalam *Pyramid of Pain* yang menuntut biaya adaptasi terbesar bagi penyerang jika berhasil dinetralkan.

---

#### Practical Capstone Challenge
**Spesifikasi Latihan:**
1. Rancang aturan deteksi Sigma teroptimasi untuk sub-teknik **MITRE ATT&CK T1055.012 (Process Hollowing)** dengan kriteria telemetri:
   * Target Event: Sysmon EID 1 (Process Create), EID 10 (ProcessAccess), dan EID 25 (ProcessTampering).
   * Kondisi: Mendeteksi adanya proses sistem yang dibuat dalam keadaan terhenti (*suspended*), diikuti penulisan memori mencurigakan atau modifikasi image base memory space oleh proses non-sistem.
2. Aturan Sigma harus memiliki metadata kepatuhan penuh, memuat pengkondisian anti-false positive dari aplikasi debugging yang sah, dan wajib dikompilasi ke format Elasticsearch EQL tanpa kesalahan sintaks.
3. Susun rencana validasi emulasi atomik menggunakan skrip uji terkontrol untuk membuktikan efektivitas deteksi tanpa menyebabkan crash pada target sistem operasi Windows Server.

---

### 19. SUMMARY & KEY TAKEAWAYS

1. **Transformasi Menuju Detection-as-Code:** Pendekatan rekayasa deteksi modern meninggalkan konfigurasi UI SIEM yang rapuh, bertransisi ke siklus hidup berbasis GitOps, pipeline CI/CD modular, validasi linting otomatis, dan manajemen repositori terpusat.
2. **Kekuatan Deklaratif Sigma dan YARA:** Standarisasi aturan menggunakan format vendor-agnostik menjamin aturan deteksi dapat dikompilasi secara instan ke beragam arsitektur teknologi SIEM/XDR masa kini tanpa harus menulis ulang logika bisnis deteksi.
3. **Siklus Tertutup Purple Teaming:** Deteksi yang tangguh tidak dapat dibangun secara asumtif. Pendekatan kolaboratif pengujian agresif menggunakan *Adversary Emulation* (seperti Atomic Red Team) menjamin kontrol keamanan divalidasi langsung terhadap data telemetri aktual.
4. **Fokus pada Puncak Piramida (TTPs):** Aturan deteksi paling bernilai tinggi adalah yang memodelkan perilaku operasional fundamental musuh pada tingkat sistem operasi (*behavioral primitives*), bukan mengandalkan artefak statis seperti hash berkas atau domain yang dapat diubah musuh secara instan.
5. **Kesadaran Evasion dan Kualitas Data:** Detection Engineer enterprise wajib memahami mekanika manipulasi internal OS (ETW unhooking, process tampering, argument injection) guna mendesain logika kueri yang kebal terhadap bypass dan efisien dalam pemrosesan data bervolume masif.

---

### 20. REFERENSI RESMI & STANDAR KEAMANAN

* **SigmaHQ Project:**
  * Specification and Core Detection Rule Repository: https://github.com/SigmaHQ/sigma
  * pySigma Backend and Pipeline Documentation: https://sigmahq-pysigma.readthedocs.io/
* **MITRE Frameworks:**
  * MITRE ATT&CK Enterprise Matrix (v14+): https://attack.mitre.org/
  * MITRE D3FEND Matrix: A Knowledge Graph of Cybersecurity Countermeasures: https://d3fend.mitre.org/
* **National Institute of Standards and Technology (NIST):**
  * NIST Special Publication 800-137: *Information Security Continuous Monitoring (ISCM) for Federal Information Systems and Organizations*.
  * NIST SP 800-61 Rev. 2: *Computer Security Incident Handling Guide*.
* **YARA Standards:**
  * VirusTotal YARA Official Documentation: https://yara.readthedocs.io/
* **Center for Internet Security (CIS):**
  * CIS Critical Security Controls v8 (Control 08: Audit Log Management; Control 13: Network Monitoring and Defense).
* **Adversary Emulation Tools:**
  * Red Canary Atomic Red Team Documentation: https://atomicredteam.io/