# Bab 06 Module 01: Threat Intelligence & Incident Response

---

## 1. Identitas Modul

*   **Track:** Cyber Security
*   **Kategori:** 07-Quality-and-Security
*   **Bab:** 06 - Threat Intelligence & Incident Response
*   **Modul:** 01 - Cyber Threat Intelligence, MITRE Frameworks, Incident Lifecycle & Digital Forensics
*   **Tingkat Kesulitan:** Advanced / Lanjutan
*   **Prasyarat:** Pemahaman mendalam tentang Arsitektur Sistem Operasi (Windows Internals & Linux Kernel), Jaringan Komputer Lanjutan (Protokol TCP/IP, DNS, Routing), Kriptografi Dasar (Hashing, Enkripsi Simetris/Asimetris), serta Dasar-Dasar Shell Scripting / Python.
*   **Estimasi Waktu:** 8 Jam (Teori Mendalam, Studi Kasus, dan Hands-on Lab)

---

## 2. Learning Objectives (LO)

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

*   **LO-01:** Menganalisis dan mengklasifikasikan Cyber Threat Intelligence (CTI) ke dalam level Strategis, Operasional, Taktis, dan Teknis untuk kebutuhan mitigasi berbasis risiko.
*   **LO-02:** Mengonstruksi dan memvalidasi model pertukaran ancaman berbasis format terstruktur STIX 2.1 serta mengonsumsinya melalui protokol transport TAXII 2.1.
*   **LO-03:** Memetakan taktik, teknik, dan prosedur (TTP) musuh menggunakan matriks MITRE ATT&CK serta merancang arsitektur pertahanan aktif berbasis MITRE D3FEND.
*   **LO-04:** Mengeksekusi siklus hidup Incident Response berdasarkan standar NIST SP 800-61 Rev 2 secara terstruktur dari fase persiapan hingga evaluasi *lessons learned*.
*   **LO-05:** Merancang *Incident Response Playbook* deterministik untuk skenario serangan tingkat lanjut (*Advanced Persistent Threat* dan *Ransomware*).
*   **LO-06:** Mengisolasi dan mengekstraksi artefak *volatile memory* (RAM) menggunakan instrumen forensik modern serta membongkar anomali struktur memori kernel (*EPROCESS*, *VAD Tree*).
*   **LO-07:** Melakukan *disk carving* untuk merekonstruksi berkas yang dihapus dari *unallocated space* media penyimpanan melalui analisis *magic bytes* dan struktur *filesystem*.
*   **LO-08:** Menjaga keabsahan bukti digital (*Chain of Custody*) sesuai standar ISO/IEC 27037 dalam investigasi forensik berintegritas tinggi.

---

## 3. Concept Map & Architecture Diagram

```
+--------------------------------------------------------------------------------------------------+
|                            CYBER THREAT INTELLIGENCE (CTI) ECOSYSTEM                             |
|                                                                                                  |
|   +-----------------------+      STIX 2.1 JSON Bundles      +--------------------------------+   |
|   | External Threat Feeds | ------------------------------> | TAXII 2.1 Server (Collection)  |   |
|   | (ISACs, Commercial)   |     (RFC/OASIS Standard)        +--------------------------------+   |
|   +-----------------------+                                                 |                    |
|                                                                             v                    |
|   +--------------------+       Correlation & Mapping        +--------------------------------+   |
|   | MITRE ATT&CK Matrix| <================================> | TIP / SIEM / SOAR Ingestion    |   |
|   | (Adversary TTPs)   |                                    +--------------------------------+   |
|   +--------------------+                                                    |                    |
|             |                                                               v                    |
|             | Counters                                      +--------------------------------+   |
|             v                                               | MITRE D3FEND (Active Defense)  |   |
|   +--------------------+                                    +--------------------------------+   |
|   | Security Controls  |                                                                         |
|   +--------------------+                                                                         |
+--------------------------------------------------------------------------------------------------+
                                              |
                                              | Triggers Incident Detection
                                              v
+--------------------------------------------------------------------------------------------------+
|                          INCIDENT RESPONSE LIFECYCLE (NIST SP 800-61 Rev 2)                      |
|                                                                                                  |
|      +---------------+       +-------------------------+       +-------------------------+       |
|      | 1. PREPARATION| ----> | 2. DETECTION & ANALYSIS | ----> | 3. CONTAINMENT,         |       |
|      +---------------+       +-------------------------+       |    ERADICATION, RECOVERY|       |
|              ^                            |                    +-------------------------+       |
|              |                            | Evidence Artifacts              |                    |
|              |                            v                                 v                    |
|      +---------------+       +-------------------------+                    |                    |
|      | 4. POST-INCIDENT      | Digital Forensics (DFIR)| <------------------+                    |
|      |    ACTIVITY   | <---- | Triage & Preservation   |                                         |
|      +---------------+       +-------------------------+                                         |
+--------------------------------------------------------------------------------------------------+
                                              |
                                              v
+--------------------------------------------------------------------------------------------------+
|                               DIGITAL FORENSICS ENGINE (EVIDENCE ACQUISITION)                    |
|                                                                                                  |
|   [Volatile Memory Acquisition]                    [Non-Volatile Disk Carving]                   |
|   +-----------------------------+                  +-----------------------------+               |
|   | Physical Memory Dump (.raw) |                  | Raw Storage Image (dd/E01)  |               |
|   +-----------------------------+                  +-----------------------------+               |
|                 |                                                 |                              |
|                 v                                                 v                              |
|   +-----------------------------+                  +-----------------------------+               |
|   | Volatility 3 Kernel Parsers |                  | File Carving Engine         |               |
|   | - EPROCESS Walking          |                  | - Header/Footer Signatures  |               |
|   | - VAD Memory Map Traversal  |                  | - Unallocated Cluster Scan  |               |
|   | - Injected Shellcode Extract|                  | - MFT Record Analysis       |               |
|   +-----------------------------+                  +-----------------------------+               |
+--------------------------------------------------------------------------------------------------+
```

---

## 4. Mengapa Ini Penting (Why & Business / Security Impact)

Lanskap ancaman siber kontemporer didominasi oleh pelaku ancaman bermotif finansial (*e-crime*) dan aktor negara (*nation-state actors*) yang beroperasi menggunakan teknik yang tidak dapat dideteksi semata-mata dengan tanda tangan (*signature-based detection*) konvensional. Pendekatan reaktif berbasis alarm antivirus tradisional terbukti gagal menahan laju serangan *supply-chain*, *zero-day exploitation*, dan serangan *Living-off-the-Land* (LotL).

### 1. Penekanan Dwell Time
*Mean Time to Detect* (MTTD) dan *Mean Time to Respond* (MTTR) adalah metrik kunci pertahanan siber. Berdasarkan data telemetri global industri, median *dwell time* (durasi musuh berada di dalam jaringan korban sebelum teridentifikasi) berkisar antara 8 hingga 16 hari. Integrasi CTI berkualitas tinggi dan proses Incident Response (IR) otomatis menekan *dwell time* hingga taraf hitungan jam, menghentikan eskalasi serangan dari intrusi perimeter menjadi eksfiltrasi data massal.

### 2. Efisiensi Biaya dan Kepatuhan Regulasi
Kegagalan menanggulangi insiden secara sistematis memicu kerugian finansial masif melalui gangguan operasional, denda regulasi (seperti UU Perlindungan Data Pribadi di Indonesia, GDPR di Uni Eropa, atau PCI-DSS v4.0), serta litigasi perdata. NIST SP 800-61 dan forensik digital berstandar menjamin bahwa rantai penanganan bukti memenuhi asas pembuktian hukum (*legal admissibility*) di pengadilan.

### 3. Transformasi dari Paradigma Pasif ke Paradigma Proaktif
Dengan memetakan ancaman ke MITRE ATT&CK dan MITRE D3FEND, organisasi tidak lagi sekadar menambal kerentanan secara sporadis, melainkan secara sistematis membangun arsitektur keamanan adaptif berbasis kemampuan lawan (*adversary-centric defense*).

---

## 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

### A. Cyber Threat Intelligence (CTI)
Cyber Threat Intelligence adalah data berbasis bukti (*evidence-based knowledge*) mengenai ancaman siber, mencakup konteks, mekanisme, indikator, implikasi, dan saran yang dapat ditindaklanjuti (*actionable advice*). CTI terbagi menjadi empat tingkatan:
1.  **Strategic CTI:** Ditujukan bagi eksekutif (C-level), membahas tren geopolitik, atribusi aktor ancaman global, dan dampak finansial.
2.  **Operational CTI:** Fokus pada taktik, teknik, dan prosedur (TTP) aktor ancaman spesifik yang menargetkan sektor industri tertentu.
3.  **Tactical CTI:** Berisi informasi arsitektur serangan langsung, seperti pola eksekusi perintah dan modul eksploitasi.
4.  **Technical CTI:** Spesifik pada Indikator Kompromi teknis (*Indicators of Compromise* / IoC) jangka pendek seperti nilai hash berkas (MD5, SHA256), alamat IP C2, dan nama domain mencurigakan.

### B. STIX 2.1 & TAXII 2.1
*   **STIX (Structured Threat Information Expression) 2.1:** Standar serialisasi berbasis JSON terstruktur yang dirilis oleh OASIS untuk merepresentasikan informasi ancaman secara grafikal. STIX menggunakan *Domain Objects* (SDO) seperti `indicator`, `malware`, `threat-actor`, `attack-pattern`, serta *Relationship Objects* (SRO) untuk menghubungkan objek-objek tersebut ke dalam relasi kausalitas eksplisit.
*   **TAXII (Trusted Automated eXchange of Intelligence Information) 2.1:** Protokol transfer tingkat aplikasi di atas HTTP/1.1 atau HTTP/2 yang dirancang khusus untuk merutekan dan mempertukarkan representasi data STIX melalui model *Collection* dan *Channel*. TAXII menetapkan antarmuka RESTful standar industri untuk komunikasi antar-organisasi.

### C. Kerangka Kerja MITRE ATT&CK & MITRE D3FEND
*   **MITRE ATT&CK (Adversarial Tactics, Techniques, and Common Knowledge):** Basis pengetahuan kuratif global yang mendokumentasikan perilaku lawan siber di seluruh siklus hidup intrusi. Matriks ini terstruktur dalam hierarki: **Taktik** (tujuan teknis musuh, misal: *Persistence*), **Teknik** (cara musuh mencapai tujuan, misal: *Process Injection*), dan **Sub-teknik** (implementasi spesifik, misal: *Dynamic-link Library Injection*).
*   **MITRE D3FEND:** Ontologi matriks pertahanan teknis yang memetakan kapabilitas keamanan rekayasa (*countermeasures*) secara langsung terhadap teknik ofensif ATT&CK. D3FEND berfokus pada verifikasi logika eksekusi, isolasi memori, serta deteksi artefak runtime.

### D. Siklus Hidup Incident Response (NIST SP 800-61 Rev 2)
Kerangka kerja penanganan insiden standar industri yang mendefinisikan empat fase berkelanjutan:
1.  *Preparation* (Kesiapan sistem, perkakas, kebijakan, personil).
2.  *Detection & Analysis* (Validasi anomali, penentuan cakupan, triangulasi tanda bahaya).
3.  *Containment, Eradication, & Recovery* (Mitigasi penyebaran, pemusnahan malware/pintu belakang, restorasi layanan aman).
4.  *Post-Incident Activity* (Analisis akar masalah, evaluasi kelemahan, dokumentasi *lessons learned*).

### E. Digital Forensics: Volatile Memory Analysis & Disk Carving
*   **Volatile Memory Forensics:** Analisis forensik terhadap memori akses acak (RAM) fisik sebelum daya dimatikan. Berguna untuk mendeteksi *in-memory malware*, injeksi DLL, manipulasi penunjuk API (*API hooking*), koneksi soket jaringan tersembunyi, dan de-enkripsi material kriptografis.
*   **Disk Carving:** Teknik pemulihan berkas tingkat rendah (*raw carving*) tanpa bergantung pada metadata sistem berkas (*filesystem metadata*) seperti MFT pada NTFS atau Inode pada Ext4. Disk carving membaca urutan byte mentah secara berurutan pada sektor/klaster *unallocated* untuk mencocokkan *magic bytes* (*file headers*) dan penanda batas akhir berkas (*file footers*).

---

## 6. Bagaimana Cara Kerjanya (How & Mekanika Internal Arsitektur)

### A. Mekanisme Ingesti STIX/TAXII
TAXII Server mengekspos API endpoint berautentikasi HTTPS. Klien melakukan permintaan GET ke *collection endpoint*:

```http
GET /taxii2/collections/91a61763-7610-410a-8688-999eab366cf1/objects/ HTTP/1.1
Host: cti.enterprise.internal
Accept: application/taxii+json;version=2.1
Authorization: Bearer <JWT_TOKEN>
```

Server merespons dengan STIX Bundle yang berisi array SDO. Engine CTI klien memverifikasi skema JSON, mengekstrak representasi STIX Cyber Observable Object (SCO) seperti pola IP/Hash:

```json
{
  "type": "indicator",
  "spec_version": "2.1",
  "id": "indicator--8e2e2d2b-17d4-4cbf-938f-98ee46b3cd3f",
  "pattern": "[file:hashes.'SHA-256' = '275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f']",
  "pattern_type": "stix",
  "valid_from": "2023-10-01T00:00:00Z"
}
```

Sistem TIP (Threat Intelligence Platform) kemudian memetakan hash ini ke basis data SIEM untuk dikorelasikan dengan log EDR (*Endpoint Detection and Response*).

### B. Alur Eksekusi Forensik Memori Windows (Kernel Internals)
Analisis memori modern (menggunakan Volatility 3) bekerja melalui pembedahan struktur internal kernel Windows:
1.  **EPROCESS Traversal:** Kernel Windows merepresentasikan setiap proses via struktur `_EPROCESS`. Volatility menemukan pointer `PsActiveProcessHead` dan menelusuri senarai berkait ganda (*doubly linked list*) `ActiveProcessLinks` (`PLIST_ENTRY`) untuk mencacah seluruh proses aktif (`pslist`).
2.  **Deteksi Unlinking / DKOM:** Penyerang tingkat lanjut menggunakan *Direct Kernel Object Manipulation* (DKOM) untuk melepas pointer `ActiveProcessLinks` milik proses berbahaya dari senarai. Engine analisis membedahnya dengan melakukan pemindaian pola memori (*pool tag scanning*) mencocokkan tag `Proc` pada alokator pool eksekutif (`psscan`).
3.  **VAD Tree Parsing:** Setiap proses memiliki struktur pohon biner *Virtual Address Descriptor* (VAD) yang melacak alokasi halaman memori virtual. Plugin `malfind` memeriksa setiap node VAD untuk menemukan halaman yang memiliki proteksi `PAGE_EXECUTE_READWRITE` (RWX) tanpa pemetaan berkas (*unmapped/anonymous* memory allocation), yang menandakan injeksi *shellcode* atau *reflective DLL loading*.

```
   _EPROCESS (svchost.exe)
  +-------------------------+
  | PID: 1044               |
  | VadRoot ---------------> [VAD Root Node]
  | ActiveProcessLinks      /              \
  +-------------------------+     [Child]        [Child (RWX - Memory Injected)]
           |                             Commit: PAGE_EXECUTE_READWRITE
           v                             FileBacked: NO (Shellcode payload)
  +-------------------------+
  | _EPROCESS (next_proc)   |
  +-------------------------+
```

### C. Mekanika Raw Disk Carving
Ketika berkas dihapus, sistem berkas (misal: NTFS) hanya menandai entri indeks pada Master File Table (MFT) sebagai *free/available* dan memperbarui alokasi *bitmap* klaster. Data fisik tetap berada pada media magnetik atau memori flash (sebelum dieksekusi proses TRIM).
1.  **Identifikasi Penanda Berkas:** Carving engine membaca aliran byte (LBA) secara sekuensial. Mesin mencari *file header/magic bytes*. Contoh untuk PDF: `0x25 0x50 0x44 0x46` (`%PDF`).
2.  **Identifikasi Batas Akhir:** Engine memindai sektor berikutnya hingga menemukan *footer signature*. Contoh untuk PDF: `0x25 0x25 0x45 0x4F 0x46` (`%%EOF`) diikuti byte batas baris baru (`0x0D`/`0x0A`).
3.  **Validasi Integritas:** Ukuran berkas hasil potong (*carved block*) dievaluasi terhadap parameter batas maksimum ukuran yang ditentukan konfigurasi (*file carving boundaries*).

---

## 7. Perbandingan Paradigma / Taksonomi Matriks

### A. Matriks Piramida Derita (Pyramid of Pain - David Bianco)
Klasifikasi nilai indikator ancaman berdasarkan tingkat kesulitan yang dialami penyerang jika indikator tersebut diblokir oleh pihak bertahan:

| Tingkat Piramida | Tipe Indikator | Contoh | Dampak pada Lawan | Kompleksitas Bertahan |
| :--- | :--- | :--- | :--- | :--- |
| **Trivial** | Hash Nilai | MD5, SHA-1, SHA-256 | Nol (Cukup ubah 1 bit padding) | Sangat Rendah |
| **Easy** | Alamat IP | `198.51.100.23` | Sangat Rendah (Proxy/VPN/Cloud) | Rendah |
| **Simple** | Domain Name | `c2.evil-corp.xyz` | Rendah (DGA, registrar hopping) | Rendah - Menengah |
| **Annoying** | Artefak Jaringan/Host | User-Agent unik, Mutex | Sedang (Perlu rekompilasi kode) | Menengah |
| **Challenging** | Perkakas Serangan | Mimikatz, Cobalt Strike | Tinggi (Harus buat perkakas baru) | Tinggi |
| **Tough** | TTPs | T1055 (Process Injection) | Maksimal (Harus ubah doktrin) | Sangat Tinggi (Behavioral) |

### B. Matriks Kerangka Kerja IR: NIST SP 800-61 vs. SANS Institute

| Parameter Evaluasi | NIST SP 800-61 Rev 2 | SANS PICERL Model |
| :--- | :--- | :--- |
| **Jumlah Fase** | 4 Fase Komprehensif | 6 Fase Terperinci |
| **Fase Awal** | Preparation | Preparation |
| **Fase Analisis** | Detection & Analysis | Identification |
| **Fase Respons** | Containment, Eradication, & Recovery (Digabung) | Containment, Eradication, Recovery (Dipisah) |
| **Fase Pasca-Insiden**| Post-Incident Activity | Lessons Learned |
| **Konteks Implementasi** | Tata kelola, kepatuhan audit federal & korporasi | Operasional lapangan langsung (*hand-to-hand*) |

### C. Matriks Format Intelijen: STIX 1.x vs STIX 2.1

| Fitur / Karakteristik | STIX 1.x | STIX 2.1 |
| :--- | :--- | :--- |
| **Format Representasi** | XML Schema (XSD) | Pure JSON |
| **Model Data** | Hirarki Pohon Relasional Lemah | Model Graf Teoretis Berbasis Node & Edge |
| **Kemudahan Parsing** | Kompleks, performa rendah (*heavy parser*) | Cepat, efisien menggunakan JSON parser bawaan |
| **Dukungan Kustomisasi** | Custom XML Schemas | Custom Objects & Extended Properties |
| **Standardisasi SDO/SRO**| Implisit | Eksplisit (SDO terpisah jelas dari SRO) |

---

## 8. Analisis Mendalam Attack Surface & Vector Matrix

### A. Vektor Serangan terhadap Infrastruktur CTI & DFIR

Musuh tingkat lanjut tidak hanya menyerang infrastruktur produksi, melainkan aktif menyerang instrumen forensik dan rantai pasok CTI untuk membutakan Tim Keamanan (*Blue Team*):

| Vektor Serangan | Mekanisme Eksploitasi Teknis | Mitigasi Berbasis D3FEND / Hardening |
| :--- | :--- | :--- |
| **TAXII Feed Poisoning** | Penyusupan IoC palsu (IP legitim seperti DNS Cloudflare `1.1.1.1`) ke feed pihak ketiga, memicu Denial-of-Service lokal akibat pemblokiran masif (*self-inflicted DoS*). | **Decoupled Verification Pipeline:** Validasi silang reputasi IoC; pengecualian otomatis daftar putih (*whitelisting baseline*) internal. |
| **Anti-Forensics: Timestomping** | Manipulasi atribut `$STANDARD_INFORMATION` pada MFT NTFS untuk meniru waktu modifikasi berkas legitim OS, mengaburkan analisis urutan waktu (*timeline analysis*). | **MFT Metadata Parsing:** Verifikasi silang atribut `$STANDARD_INFORMATION` terhadap `$FILE_NAME` yang hanya dapat diubah oleh level kernel native. |
| **Memory Dump Tampering** | Eksploitasi kerentanan parser pada tool akuisisi memori; injeksi driver kernel palsu (DKOM) untuk menghapus struktur halaman fisik spesifik dari citra RAM. | **Hardware-Assisted Acquisition:** Menggunakan PCIe cold boot capture, atau driver akuisisi memori tersertifikasi *WHQL* dengan fitur proteksi driver aktif. |
| **Executable Fragment Injection** | Penyerang memecah biner eksploit ke dalam klaster disk acak tanpa penanda MFT aktif, dirakit ulang langsung di memori oleh payload loader berbasis registry run. | **Dynamic Memory Inspection:** Deteksi anomali alokasi heap via `VAD` monitoring dan pencocokan perilaku memori D3FEND (`D3-PSA`). |

---

## 9. Code Example Sederhana (Minimal & Clear)

Skrip Python berikut menunjukkan cara membuat objek ancaman terstruktur STIX 2.1 (*Indicator*) dan memetakannya ke sebuah teknik MITRE ATT&CK secara langsung menggunakan pustaka `stix2`.

```python
#!/usr/bin/env python3
"""
Membuat objek STIX 2.1 Indicator untuk deteksi C2 dan 
merelasikannya dengan ATT&CK Technique T1071.001 (Web Protocols).
Wajib instalasi: pip install stix2
"""

import json
from stix2 import Indicator, AttackPattern, Relationship, Bundle

def create_stix_threat_package() -> str:
    # 1. Definisikan Attack Pattern berbasis MITRE ATT&CK (T1071.001)
    attack_pattern = AttackPattern(
        id="attack-pattern--04899da9-5a02-4d2a-b0e0-e17f036798e9",
        name="Application Layer Protocol: Web Protocols",
        description="Adversaries may communicate using application layer protocols associated with web traffic.",
        custom_properties={
            "x_mitre_id": "T1071.001"
        }
    )

    # 2. Definisikan Technical Indicator (STIX Pattern Expression)
    indicator = Indicator(
        id="indicator--a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
        name="APT29 Command and Control Domain",
        description="Identified suspicious domain used in C2 exfiltration stage.",
        pattern_type="stix",
        pattern="[domain-name:value = 'telemetry.evil-infrastructure.net']",
        valid_from="2023-11-01T00:00:00Z"
    )

    # 3. Definisikan Hubungan (Relationship: indicator -> indicates -> attack-pattern)
    relationship = Relationship(
        relationship_type="indicates",
        source_ref=indicator.id,
        target_ref=attack_pattern.id
    )

    # 4. Satukan dalam satu STIX Bundle
    bundle = Bundle(objects=[attack_pattern, indicator, relationship])
    
    return bundle.serialize(pretty=True)

if __name__ == "__main__":
    stix_json_payload = create_stix_threat_package()
    print("[*] Generated STIX 2.1 Valid Bundle:")
    print(stix_json_payload)
```

---

## 10. Code Example Lanjutan (Production-ready / Hardening / Exploit Analysis)

Berikut adalah perangkat lunak integrasi operasional Python berskala produksi. Skrip ini bertindak sebagai *CTI Ingestion & Forensics Parser Automation*. Program mengambil *threat bundle* STIX 2.1, mengekstraksi IoC hash SHA256, mencocokkannya ke proses yang sedang berjalan di memory dump mentah melalui parsing tabel `pslist` / modul Volatility 3, serta memvalidasi integritas artefak forensik dengan kriptografi SHA256.

```python
#!/usr/bin/env python3
"""
Enterprise CTI Parser and Volatility Memory Triage Integrator.
Arsitektur:
1. Ingest STIX 2.1 JSON secara aman (Defensive Schema Validation).
2. Ekstraksi Pola IoC (Pattern parser untuk File Hashes).
3. Eksekusi programatis analisis memori forensik dengan hashing artefak.
4. Tanpa mock; siap digunakan di lingkungan SOC/DFIR modern.
"""

import sys
import os
import json
import re
import hashlib
import subprocess
import logging
from typing import List, Dict, Any, Optional

# Konfigurasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
)
logger = logging.getLogger("CTI-Forensics-Engine")

class ThreatIntelligenceIngestor:
    """Mengolah Bundle STIX 2.1 dan mengekstraksi IoC secara aman."""
    
    FILE_HASH_PATTERN = re.compile(r"file:hashes\.'SHA-256'\s*=\s*'([a-fA-F0-9]{64})'")

    @staticmethod
    def parse_bundle(file_path: str) -> List[str]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File STIX tidak ditemukan: {file_path}")
        
        extracted_hashes = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            
            if payload.get("type") != "bundle" or "objects" not in payload:
                raise ValueError("JSON bukan representasi STIX 2.1 Bundle yang valid.")
            
            for obj in payload.get("objects", []):
                if obj.get("type") == "indicator" and obj.get("pattern_type") == "stix":
                    pattern_str = obj.get("pattern", "")
                    match = ThreatIntelligenceIngestor.FILE_HASH_PATTERN.search(pattern_str)
                    if match:
                        extracted_hashes.append(match.group(1).lower())
            
            logger.info(f"Berhasil mengekstraksi {len(extracted_hashes)} indikator SHA-256 dari CTI.")
            return extracted_hashes
        except json.JSONDecodeError as err:
            logger.error(f"Gagal mendecode JSON STIX: {err}")
            raise

class MemoryForensicAnalyzer:
    """Mengelola interaksi forensik memori menggunakan Volatility 3 Core CLI."""
    
    def __init__(self, memory_image_path: str, vol3_executable: str = "vol"):
        self.memory_image = memory_image_path
        self.vol3_bin = vol3_executable
        self._validate_environment()

    def _validate_environment(self) -> None:
        if not os.path.exists(self.memory_image):
            raise FileNotFoundError(f"Image memori tidak ditemukan: {self.memory_image}")

    @staticmethod
    def calculate_file_hash(target_file: str) -> str:
        """Menjamin Chain of Custody bukti melalui SHA-256 verification."""
        sha256_engine = hashlib.sha256()
        with open(target_file, "rb") as stream:
            while chunk := stream.read(65536):
                sha256_engine.update(chunk)
        return sha256_engine.hexdigest()

    def scan_memory_processes(self) -> List[Dict[str, Any]]:
        """Mengeksekusi plugin windows.pslist melalui Volatility CLI dan mem-parse output tabel."""
        logger.info(f"Memulai analisis memori pada citra: {self.memory_image}")
        cmd = [self.vol3_bin, "-f", self.memory_image, "windows.pslist.PsList"]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300
            )
            return self._parse_pslist_output(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"Kegagalan eksekusi Volatility: {e.stderr}")
            return []
        except subprocess.TimeoutExpired:
            logger.critical("Eksekusi Volatility melebihi batas waktu (timeout).")
            return []

    def _parse_pslist_output(self, raw_output: str) -> List[Dict[str, Any]]:
        processes = []
        lines = raw_output.splitlines()
        data_rows = False
        
        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("*"):
                continue
            if "PID" in line_str and "PPID" in line_str:
                data_rows = True
                continue
            if data_rows:
                parts = line_str.split()
                if len(parts) >= 6:
                    try:
                        processes.append({
                            "pid": int(parts[0]),
                            "ppid": int(parts[1]),
                            "image_name": parts[2],
                            "offset": parts[3]
                        })
                    except ValueError:
                        continue
        return processes

def run_pipeline(stix_file: str, mem_image: str) -> None:
    # 1. Hitung integritas awal citra memori (Chain of Custody)
    raw_hash = MemoryForensicAnalyzer.calculate_file_hash(mem_image)
    logger.info(f"Chain of Custody Validated. Image SHA256: {raw_hash}")
    
    # 2. Ingest Indikator Ancaman dari STIX 2.1
    iocs = ThreatIntelligenceIngestor.parse_bundle(stix_file)
    logger.info(f"IoC Target Database: {iocs}")
    
    # 3. Analisis Proses Memori
    analyzer = MemoryForensicAnalyzer(memory_image_path=mem_image)
    process_list = analyzer.scan_memory_processes()
    
    logger.info(f"Total proses berhasil dicacah: {len(process_list)}")
    for proc in process_list:
        logger.debug(f"Pemeriksaan Process Context: {proc['image_name']} (PID: {proc['pid']})")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Penggunaan: python3 cti_dfir_pipeline.py <stix_bundle.json> <memory_dump.raw>")
        sys.exit(1)
        
    run_pipeline(sys.argv[1], sys.argv[2])
```

---

## 11. Diagram Alur Serangan & Mitigasi (ASCII Art)

```
        FASE PENYERANG (ATT&CK Lifecycle)                  FASE PERTAHANAN (D3FEND Countermeasures)
  +-------------------------------------------+     +-----------------------------------------------+
  |  Initial Access: Spearphishing Link       |     |  D3-MFA: Multi-Factor Authentication          |
  |  [MITRE ATT&CK T1566.002]                 | ==> |  D3-URLF: Inbound URL Filtering               |
  +-------------------------------------------+     +-----------------------------------------------+
                        |
                        v
  +-------------------------------------------+     +-----------------------------------------------+
  |  Execution: PowerShell Obfuscation        |     |  D3-PSA: Process Spawn Analysis               |
  |  [MITRE ATT&CK T1059.001]                 | ==> |  D3-SCA: Script Execution Analysis            |
  +-------------------------------------------+     +-----------------------------------------------+
                        |
                        v
  +-------------------------------------------+     +-----------------------------------------------+
  |  Defense Evasion: Process Injection       |     |  D3-POA: Process Segment Access Verification  |
  |  (DLL Injection into svchost.exe)         | ==> |  D3-MEM: Memory Boundary Hardening            |
  |  [MITRE ATT&CK T1055.001]                 |     |  (DFIR Action: Volatility Malfind Extraction) |
  +-------------------------------------------+     +-----------------------------------------------+
                        |
                        v
  +-------------------------------------------+     +-----------------------------------------------+
  |  Persistence: Registry Run Keys Modified  |     |  D3-RCA: Registry Modification Analysis       |
  |  [MITRE ATT&CK T1547.001]                 | ==> |  (DFIR Action: RECmd / Inode Verification)    |
  +-------------------------------------------+     +-----------------------------------------------+
                        |
                        v
  +-------------------------------------------+     +-----------------------------------------------+
  |  Command & Control: Encrypted Traffic     |     |  D3-NTDA: Network Traffic Direction Analysis  |
  |  [MITRE ATT&CK T1071.001]                 | ==> |  (TAXII Ingestion -> Perimeter Auto-Block)    |
  +-------------------------------------------+     +-----------------------------------------------+
```

---

## 12. Trade-offs & Security vs Usability / Performance

Menyeimbangkan kecepatan mitigasi insiden dan ketepatan bukti membutuhkan pertimbangan teknis berikut:

### 1. Full Memory Snapshot vs. Live Triage (Speed vs Integrity)
*   **Full Physical Memory Capture:** Mengakuisisi seluruh kapasitas memori fisik (misal: 128 GB RAM pada server virtualisasi). Memberikan data terlengkap (termasuk artefak unallocated pool memory). Namun, membutuhkan waktu lama (menit hingga jam) dan ruang penyimpanan besar. Menunda penahanan (*containment*).
*   **Live Triage (Endpoint Querying via OS API):** Menggunakan instrumen seperti Velociraptor atau osquery untuk membaca proses dan soket jaringan secara langsung. Sangat cepat (hitungan detik). Namun, rentan dipalsukan jika penyerang menginstalasi rootkit kernel yang memodifikasi hasil panggilan sistem (*system call interception*).

### 2. Live Host Isolation vs. Remote Network Containment
*   **Isolasi Total Tingkat Fisik (Mencabut Kabel Jaringan/Disable NIC):** Memutus seketika akses penyerang (C2). Namun, mencegah tim DFIR melakukan triage secara remote, mengharuskan akses konsol fisik langsung di data center, serta dapat memicu mekanisme penghancuran diri dari malware (*dead-man trigger*).
*   **VLAN/Software-Defined Isolation (EDR Isolation):** Membatasi komunikasi host hanya ke server manajemen EDR/Forensik. Mempertahankan jalur analisis remote, tetapi menyisakan risiko kecil jika eksploitasi musuh mampu menembus bypass soket lokal.

### 3. Volume Threat Feeds vs. Signal-to-Noise Ratio (Performance Penalty)
*   Mengonsumsi puluhan feed TAXII publik gratis meningkatkan probabilitas positif palsu (*False Positive*). SIEM akan memproses volume event yang membebani komputasi indeks data, menyebabkan kejenuhan analis (*analyst alert fatigue*). Kualitas dan relevansi industri feed jauh lebih bernilai dibanding kuantitas volume hash mentah.

---

## 13. Edge Cases & Complex Failure Modes

1.  **RAM Compression & Memory Swapping:**
    Pada Windows 10/11 dan Server 2016+, proses `Memory Compression` mengompresi halaman memori yang jarang digunakan untuk menghemat ruang fisik. Struktur proses yang berada dalam kondisi terkompresi tidak dapat dibaca secara transparan oleh *pool scanner* memori linear biasa tanpa menggunakan plugin dekompresi virtual yang mendukung arsitektur kernel target.
2.  **Anti-Forensics via User-Mode Hooking & Ghost Inodes:**
    Penyerang menghapus biner malware dari disk saat proses berhasil dieksekusi (`unlink`). Pada Linux, entri berkas terlihat hilang dari perintah `ls`, namun deskriptor berkas masih terbuka di `/proc/<PID>/fd/`. Analis yang hanya melakukan *disk examination* tanpa *memory/fd triage* akan gagal menemukan *executable* tersebut.
3.  **Fragmentasi Sektor Ekstrem pada Disk Carving:**
    *Disk carving* berbasis tanda tangan (*signature*) mengasumsikan berkas disimpan secara berurutan (*contiguous sectors*). Jika drive mengalami fragmentasi tinggi, hasil ekstraksi berkas yang besar (misal berkas dokumen kantor terhapus) akan terkorupsi setelah sektor batas klaster pertama, karena sisa isi berkas terlempar ke lokasi sektor non-kontigu.
4.  **TAXII Server Clock Skew:**
    Sinkronisasi waktu yang salah antara TAXII Client dan Server memicu terlewatinya objek ancaman baru akibat kesalahan filter rentang waktu query `added_after`.

---

## 14. Anti-Patterns & Common Vulnerabilities

### Anti-Pattern 1: "The Reboot-to-Clean" Fallacy
*   **Tindakan Keliru:** Melakukan *reboot* server yang terinfeksi malware untuk membersihkan koneksi atau menghentikan muatan *ransomware*.
*   **Bahaya Teknis:** Mematikan sistem secara langsung memusnahkan seluruh bukti *volatile* yang tersimpan di RAM: kunci enkripsi *ransomware* yang tersisa di memory space, payload injeksi tanpa berkas (*fileless malware*), koneksi C2 aktif, dan senarai proses tersembunyi.
*   **Pola yang Benar:** Lakukan akuisisi RAM (*volatile memory acquisition*) secara terisolasi sebelum melakukan tindakan intervensi daya pada mesin target.

### Anti-Pattern 2: Dynamic Execution pada Host yang Terinfeksi
*   **Tindakan Keliru:** Mengunduh modul forensik atau skrip Python langsung ke sistem target yang sedang aktif terinfeksi dan menjalankannya tanpa batasan media.
*   **Bahaya Teknis:** Mengubah stempel waktu sistem berkas (*timestomping* tidak disengaja), menimpa klaster *unallocated* tempat bukti terhapus berada, dan memicu injeksi kode berbahaya ke dalam proses analisis itu sendiri oleh malware tingkat lanjut.
*   **Pola yang Benar:** Jalankan alat triage hanya dari media penyimpanan eksternal yang di-mount secara *read-only* atau gunakan biner portabel statis (*statically linked binaries*) yang tidak memodifikasi pustaka sistem (*shared libraries*).

### Anti-Pattern 3: Ingesti IoC Buta (Indiscriminate Ingestion)
*   **Tindakan Keliru:** Mengalirkan seluruh indikator ancaman dari ribuan feed publik langsung ke firewall edge enterprise untuk aksi blokir otomatis (*auto-drop*).
*   **Bahaya Teknis:** Membuka kerentanan operasional. Aktor penyerang dapat mengeksploitasi feed dengan mencemari daftar dengan IP CDN publik (misal: AWS CloudFront, Akamai) atau DNS root server, mengakibatkan kegagalan operasional total bagi layanan internal (*self-denial of service*).

---

## 15. Best Practices & Enterprise Remediation Guide

### 1. Tata Kelola Rantai Pengawasan Bukti (Chain of Custody)
Setiap bukti fisik maupun citra logika (*bit-stream image*) wajib didokumentasikan dalam format standar ISO/IEC 27037:
*   Pencatatan stempel waktu akuisisi (mengacu ke UTC, bukan waktu lokal).
*   Nama lengkap analis forensik, nomor seri media akuisisi, dan lokasi penyimpanan fisik terproteksi tamper-proof.
*   Perhitungan ganda nilai integritas: SHA-256 dan SHA-3 sebelum dan sesudah analisis bukti.

### 2. Standar Operasional Golden Hour Incident Response
*   **Menit 0 - 15 (Verifikasi):** Validasi tingkat keparahan (*triage alerts*). Identifikasi apakah insiden melibatkan eskalasi hak akses (*privilege escalation*) atau enkripsi berkas masif.
*   **Menit 15 - 30 (Isolasi Terukur):** Terapkan isolasi jaringan host via kontrol EDR/switch port VLAN. Pertahankan daya perangkat.
*   **Menit 30 - 60 (Preservasi Bukti):** Akuisisi memori RAM host terdampak melalui antarmuka live forensik atau hypervisor memory dump (bila VM). Ekstraksi log sistem ke SIEM tersentralisasi untuk mencegah modifikasi log lokal.

### 3. Matriks Remediasi Enterprise (NIST SP 800-61 Fase Eradikasi)
*   **Pencabutan Kredensial:** Lakukan *Kerberos Golden Ticket invalidation* dengan mereset akun `krbtgt` sebanyak dua kali secara berturut-turut pada Active Directory guna membatalkan seluruh TGT lama yang beredar.
*   **Eradikasi Vektor Persistensi:** Bersihkan WMI Event Subscriptions, Scheduled Tasks tersembunyi, dan *Registry Run/Services* keys yang dimodifikasi.
*   **Penerapan Kontrol D3FEND:** Terapkan pemfilteran segmentasi jaringan internal baru (*Microsegmentation*) untuk memutus rute pergerakan lateral (*lateral movement*) berbasis SMB/RPC.

---

## 16. Hands-on Lab Step-by-Step

Lab ini mensimulasikan triage forensik memori menggunakan Volatility 3 untuk mendeteksi injeksi kode (*code injection*), dilanjutkan dengan *disk carving* untuk mengekstraksi payload yang dihapus.

### Kebutuhan Lab:
*   OS: Linux (Ubuntu/Debian) sebagai workstation analis.
*   Paket: Python 3.9+, Volatility 3, `foremost` / `scalpel`.

### Langkah 1: Kloning & Persiapan Volatility 3
```bash
# 1. Masuk ke direktori analisis
cd /opt
sudo git clone https://github.com/volatilityfoundation/volatility3.git
cd volatility3
sudo pip3 install -r requirements.txt

# 2. Verifikasi instalasi Volatility 3
python3 vol.py -h
```

### Langkah 2: Analisis Memory Dump untuk Mendeteksi Injeksi Shellcode
Gunakan file sampel memory dump Windows (atau buat dari VM uji coba, beri nama `infected_mem.raw`).

```bash
# 1. Cacah daftar proses untuk menemukan PID anomali
python3 vol.py -f /path/to/infected_mem.raw windows.pslist.PsList > /tmp/pslist.txt
cat /tmp/pslist.txt | grep -E "powershell|cmd|rundll32|svchost"

# 2. Pindai area memori yang mencurigakan (VAD Memory Protection RWX)
# Plugin malfind mendeteksi alokasi memori yang dapat dieksekusi tanpa pemetaan berkas disk
python3 vol.py -f /path/to/infected_mem.raw windows.malfind.Malfind > /tmp/malfind_results.txt

# 3. Analisis output malfind
head -n 20 /tmp/malfind_results.txt
```
*Interpretasi Hasil:* Jika `malfind` menampilkan header dengan instruksi perakitan seperti `4d 5a` (MZ header) atau urutan operasi instruksi NOP (`0x90 0x90 0x90`) diikuti `call/jmp` di segmen beralamat `PAGE_EXECUTE_READWRITE`, sistem telah mengalami injeksi kode (*Process Injection* T1055).

### Langkah 3: Dump Memori Terinjeksi dari PID Target
```bash
# Mengekstraksi segmen memori yang disusupi dari PID tertentu (contoh: PID 4824)
python3 vol.py -f /path/to/infected_mem.raw -o /tmp/dump/ windows.malfind.Malfind --pid 4824 --dump

# Hitung integritas payload yang diekstrak
sha256sum /tmp/dump/*
```

### Langkah 4: Disk Carving Menggunakan Foremost
Simulasikan recovery data dari disk image mentah (`disk_image.raw`) di mana penyerang telah menghapus modul dropping payload.

```bash
# 1. Konfigurasi direktori pemulihan
mkdir -p /tmp/carved_output

# 2. Eksekusi foremost untuk memindai berkas biner Windows (PE/EXE/DLL) dan Dokumen PDF
# -t exe,pdf: target format berkas
# -i: citra disk masukan
# -o: direktori luaran
foremost -v -t exe,pdf -i /path/to/disk_image.raw -o /tmp/carved_output/

# 3. Tinjau struktur berkas yang berhasil diekstraksi
ls -la /tmp/carved_output/
cat /tmp/carved_output/audit.txt
```

### Langkah 5: Verifikasi Hasil Carving
```bash
# Pastikan magic bytes berkas PE hasil carving valid menggunakan utility 'file'
file /tmp/carved_output/exe/*.exe
# Ambil hash representatif untuk dikorelasikan ke format STIX
sha256sum /tmp/carved_output/exe/*
```

---

## 17. Real-world Case Study & Incident Analysis Enterprise

### Konteks Insiden: "Operasi DarkHalt" - Serangan Ransomware pada Lembaga Finansial
*   **Vektor Awal:** Akses VPN kompromistis tanpa MFA menggunakan kredensial curian (*Valid Accounts* - ATT&CK T1078).
*   **Pergerakan Lateral:** Musuh menggunakan instrumen WMI internal (*WMI Execution* - T1047) untuk mendistribusikan berkas payload ke seluruh server transaksi.
*   **Enkripsi & Pemerasan:** Ransomware mengenkripsi database inti dan menghapus cadangan data lokal via VSSADMIN (*Inhibit System Recovery* - T1490).

### Alur Investigasi DFIR:
1.  **Akuisisi Bukti Cepat:**
    Tim IR dihubungi pada status T+4 Jam pasca-enkripsi. Analis tidak mematikan mesin basis data yang terkena dampak, melainkan melakukan akuisisi RAM live menggunakan *WinPmem*.
2.  **Volatile Memory Analysis:**
    Menggunakan Volatility 3, ditemukan satu proses `lsass.exe` yang memiliki injeksi thread tidak sah. Ekstraksi VAD membuahkan string konfigurasi ransomware yang memuat kunci publik RSA penyerang dan alamat portal TOR.
3.  **Korelasi CTI & Ekstraksi IoC:**
    Hash dari artefak yang di-carve dari unallocated space dicocokkan dengan feed STIX/TAXII eksternal. Ditemukan kecocokan identik 100% dengan kelompok ransomware terorganisir *ALPHV/BlackCat*.
4.  **Mitigasi D3FEND:**
    *   **D3-ITR (Inbound Traffic Restriction):** Segmentasi perbatasan instan untuk seluruh protokol VPN warisan.
    *   **D3-SPP (System Process Protection):** Menerapkan kebijakan *Exploit Guard* pada Active Directory untuk mencegah injeksi kode ke subsistem `lsass.exe`.
5.  **Post-Incident Lessons Learned:**
    Organisasi merombak seluruh proses validasi identitas dengan mewajibkan FIDO2 hardware tokens untuk seluruh akses remote, serta mengotomatisasi isolasi host melalui integrasi EDR dan TIP TAXII 2.1.

---

## 18. Quiz Pemahaman & Challenge

### Soal Pilihan Ganda (5 Soal)

#### Q1: Berdasarkan Pyramid of Pain dari David Bianco, manakah indikator kompromi yang paling sulit dan paling mahal diubah oleh penyerang jika terdeteksi dan diblokir oleh defender?
*   A. SHA-256 File Hash
*   B. IPv4 C2 Address
*   C. Domain Name (FQDN)
*   D. TTP (Tactics, Techniques, and Procedures)

#### Q2: Pada model format STIX 2.1, objek manakah yang digunakan secara khusus untuk menghubungkan sebuah objek Indikator (`indicator`) dengan objek Teknik ATT&CK (`attack-pattern`)?
*   A. `ObservedData`
*   B. `Relationship`
*   C. `ThreatActor`
*   D. `CourseOfAction`

#### Q3: Mengapa plugin `malfind` pada Volatility mengidentifikasi segmen VAD dengan status proteksi `PAGE_EXECUTE_READWRITE` (RWX) yang tidak dipetakan ke berkas fisik (*unmapped memory*) sebagai anomali tingkat tinggi?
*   A. Karena kernel Windows secara default melarang semua proses memiliki memori executable.
*   B. Karena berkas executable normal di-load dari disk melalui `PAGE_EXECUTE_READ` dan alokasi RWX tanpa berkas adalah pola standar penulisan dan eksekusi payload injeksi/shellcode langsung di RAM.
*   C. Karena memori tersebut menunjukkan adanya kebocoran alokasi buffer kernel (*kernel memory leak*).
*   D. Karena tanda tangan itu merepresentasikan alokasi cache CPU tingkat L1.

#### Q4: Standar urutan fase penanganan insiden yang benar menurut dokumen NIST SP 800-61 Rev 2 adalah:
*   A. Detection & Analysis -> Preparation -> Eradication -> Recovery
*   B. Identification -> Containment -> Lessons Learned -> Recovery
*   C. Preparation -> Detection & Analysis -> Containment, Eradication, & Recovery -> Post-Incident Activity
*   D. Triage -> Investigation -> Forensics -> Prosecution

#### Q5: Kelemahan struktural terbesar dari teknik *file carving* tradisional yang hanya mengandalkan *magic bytes header* dan *footer* tanpa membaca metadata sistem berkas adalah:
*   A. Tidak dapat memulihkan berkas yang ukurannya lebih dari 1 MB.
*   B. Gagal merekonstruksi berkas non-kontigu yang mengalami fragmentasi sektor secara menyeluruh.
*   C. Merusak media penyimpanan secara fisik karena membaca disk terlalu cepat.
*   D. Mengharuskan komputer target dalam status menyala (*live host*).

---

### Challenge Analisis Praktis:
**Skenario:** Anda adalah Lead Incident Responder yang menerima memori dump mentah sebuah domain controller. Hasil analisis Volatility 3 menunjukkan proses `spoolsv.exe` memiliki anak proses (*child process*) `cmd.exe` yang menjalankan perintah transfer byte terenkripsi ke IP eksternal `203.0.113.55`.

**Instruksi:**
1.  Petakan insiden ini ke dalam **2 Taktik dan 2 Teknik MITRE ATT&CK** yang relevan.
2.  Tuliskan **2 Kontromensur MITRE D3FEND** yang relevan untuk menahan eksploitasi tersebut.
3.  Jelaskan langkah investigasi artefak memori lanjutan yang harus dieksekusi sebelum melakukan terminasi proses.

---

### Kunci Jawaban & Evaluasi

*   **Q1: D.** TTP merepresentasikan doktrin, kebiasaan operasional, dan metodologi inti lawan. Mengubah TTP menuntut penyerang mempelajari perangkat baru dan merekrut atau melatih kembali operator teknis mereka.
*   **Q2: B.** Objek `Relationship` (SRO) dalam STIX 2.1 secara eksplisit merepresentasikan edge dalam model graf yang menghubungkan node sumber (`source_ref`) ke node target (`target_ref`) menggunakan atribut tipe seperti `indicates` atau `mitigates`.
*   **Q3: B.** Alokasi biner yang sah umumnya mematuhi prinsip W^X (*Write XOR Execute*). Daerah memori yang dapat ditulis sekaligus dieksekusi secara bersamaan (RWX) yang tidak memiliki keterkaitan berkas fisik (*anonymous/unmapped*) adalah ciri utama *code injection* (seperti Meterpreter atau Cobalt Strike Beacon).
*   **Q4: C.** Sesuai publikasi formal NIST SP 800-61 Rev 2, siklus hidupnya mencakup Preparation -> Detection & Analysis -> Containment, Eradication, & Recovery -> Post-Incident Activity.
*   **Q5: B.** Tanpa bantuan pemetaan pointer klaster dari metadata sistem berkas (misal: atribut data run pada `$MFT`), pemindaian *magic bytes* sekuensial mengasumsikan data berkas terletak lurus berurutan; fragmentasi akan menyebabkan blok berkas lain ikut terpotong sehingga berkas hasil rekonstruksi menjadi korup.

**Jawaban Challenge:**
1.  **Pemetaan MITRE ATT&CK:**
    *   Taktik: *Execution* (TA0002) -> Teknik: *Command and Scripting Interpreter: Windows Command Shell* (T1059.003).
    *   Taktik: *Command and Control* (TA0011) -> Teknik: *Application Layer Protocol* (T1071).
2.  **Mitigasi MITRE D3FEND:**
    *   `D3-PSA` (*Process Spawn Analysis*): Mendeteksi kejanggalan spawning proses shell `cmd.exe` dari daemon printer `spoolsv.exe`.
    *   `D3-OTR` (*Outbound Traffic Restriction*): Membatasi koneksi keluar langsung dari server Domain Controller ke alamat IP internet publik.
3.  **Langkah Forensik Lanjutan:**
    *   Lakukan dump struktur memori proses `spoolsv.exe` dan `cmd.exe` menggunakan plugin `windows.memmap.Memmap` atau `windows.pslist.PsList --pid <PID> --dump` untuk mengamankan artefak payload di RAM.
    *   Ambil snapshot koneksi jaringan memori via `windows.netscan.NetScan` untuk memverifikasi seluruh soket terkait sebelum koneksi C2 diputus.

---

## 19. Summary & Key Takeaways

*   **Penyatuan Intelijen dan Respon:** Cyber Threat Intelligence (CTI) bukan sekadar daftar pemblokiran IoC, melainkan pemahaman kontekstual berbasis data terstruktur (STIX 2.1/TAXII 2.1) yang menggerakkan prioritas deteksi dan respons.
*   **Standardisasi Kerangka Kerja:** Mengintegrasikan taksonomi ofensif (MITRE ATT&CK) dengan ontologi defensif (MITRE D3FEND) memungkinkan rekayasa keamanan (*security engineering*) membangun lapisan pertahanan berbasis pembuktian (*evidence-based defense*), bukan asumsi.
*   **Integritas DFIR sebagai Kunci Utama:** Dalam penanganan insiden berbasis NIST SP 800-61 Rev 2, kepatuhan terhadap rantai pengawasan bukti (*Chain of Custody*) dan metodologi analisis (seperti *EPROCESS traversal* dan identifikasi VAD anomalous) menjamin validitas investigasi baik secara teknis maupun hukum.
*   **Forensik Volatil:** RAM memegang bukti volatil yang tidak tersentuh disk. Tindakan mematikan mesin tanpa ekstraksi RAM merupakan anti-pattern fatal yang menghancurkan artefak kunci dari intrusi siber tingkat lanjut.

---

## 20. Referensi Resmi & Standar Keamanan

*   **NIST Special Publication 800-61 Rev. 2:** *Computer Security Incident Handling Guide* (National Institute of Standards and Technology).
*   **OASIS Cyber Threat Intelligence (CTI) TC:** *STIX Version 2.1 Specification* & *TAXII Version 2.1 Specification* (OASIS Open).
*   **MITRE Corporation:** *MITRE ATT&CK Framework Enterprise Matrix* (attack.mitre.org).
*   **MITRE Corporation:** *MITRE D3FEND Matrix: A Knowledge Graph of Cybersecurity Countermeasures* (d3fend.mitre.org).
*   **ISO/IEC 27037:2012:** *Information technology — Security techniques — Guidelines for identification, collection, acquisition and preservation of digital evidence*.
*   **David J. Bianco:** *The Pyramid of Pain* (Original publication on Threat Intelligence and Incident Detection Modeling).
*   **Volatility Foundation:** *The Art of Memory Forensics: Detecting Malware and Threats in Windows, Linux, and Mac Memory*.