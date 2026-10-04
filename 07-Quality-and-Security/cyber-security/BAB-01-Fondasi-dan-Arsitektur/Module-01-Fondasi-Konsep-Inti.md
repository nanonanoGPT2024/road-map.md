# BAB 01: FONDASI KEAMANAN SISTEM & REKAYASA ANCAMAN
## MODUL 01: Core Security Architecture, CIA/DAD Triad, Threat Modeling (STRIDE), dan Analisis Permukaan Serangan

---

### 1. Judul Modul & Target Pembaca

*   **Jalur Pembelajaran:** Cyber Security Engineering & Architecture
*   **Target Pembaca:** Security Engineers, Systems Architects, DevSecOps Engineers, dan Senior Backend Engineers yang bertransisi ke ranah *Defensive Engineering* dan *Infrastructure Security*.
*   **Prasyarat Pengetahuan:**
    *   Pemahaman mendalam mengenai arsitektur sistem operasi (POSIX primitives, ring privilege, memory management).
    *   Pemahaman stack protokol jaringan TCP/IP (L3 hingga L7 routing, switching, handshake mekanik).
    *   Familiaritas dengan bahasa pemrograman Python atau Go untuk otomatisasi sistem.
    *   Dasar-dasar aljabar modular dan teori bilangan (prasyarat kriptografi dasar).

```
+-------------------------------------------------------------------------+
| PRASYARAT: Linux Kernel Internals & TCP/IP State Machine                |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
| TARGET: Keahlian Membangun Sistem Resilien & Evaluasi Ancaman Deterministis |
+-------------------------------------------------------------------------+
```

---

### 2. Peta Konsep Mental (Mental Model & System Boundary)

Model mental fundamental dalam rekayasa keamanan siber berpusat pada penolakan terhadap asumsi *implicit trust*. Sistem digital adalah sekumpulan *finite state machines* (FSM) yang beroperasi di atas media komunikasi yang secara inheren tidak aman. Setiap batas proses, pemanggilan jaringan, soket IPC (*Inter-Process Communication*), atau eksekusi fungsi di ruang pengguna (*user space*) mendefinisikan sebuah **Security Boundary** (Batas Keamanan).

```
       UNTRUSTED DOMAIN (External Network / Attacker Controlled)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                                 │ [Inbound Traffic]
                                 ▼
                     +───────────────────────+
                     │  Perimeter Filtering  │ <── Rate Limiting, WAF, mTLS
                     +───────────┬───────────+
                                 │
   TRUST DOMAIN BOUNDARY (Zero-Trust Transition Vector)
  ===============================│=================================
                                 ▼
                     +───────────────────────+
                     │ Ingestion / Parsing   │ <── Input Validation (Untrusted)
                     +───────────┬───────────+
                                 │
                  ┌──────────────┴──────────────┐
                  ▼                             ▼
       +─────────────────────+       +─────────────────────+
       │ Execution Engine A  │ <───> │ Execution Engine B  │
       │ (Least Privilege)   │  IPC  │ (Least Privilege)   │
       +──────────┬──────────+       +──────────┬──────────+
                  │                             │
  ================│=============================│==================
  KERNEL / STORAGE BOUNDARY (Hardware Root of Trust, Secure Enclave)
                  ▼                             ▼
       +───────────────────────────────────────────────────+
       │ Cryptographic Keystore / Audited Persistence Engine │
       +───────────────────────────────────────────────────+
```

Keamanan bukanlah status biner (aman vs. tidak aman), melainkan fungsi matematika dari **probabilitas kegagalan**, **biaya asimetris penyerangan** (*attacker economics*), dan **nilai aset yang dipertahankan**. Rekayasa pertahanan memetakan seluruh aliran data yang melintasi batas sistem, mengidentifikasi asumsi yang dapat dieksploitasi oleh adversari, dan menetapkan kontrol deterministik untuk memastikan integritas operasional.

---

### 3. Learning Objectives (Standar Taksonomi Bloom Terbalik)

Pada akhir modul ini, Anda memiliki kapabilitas terukur untuk:
1.  **Menganalisis** arsitektur komputasi terdistribusi menggunakan paradigma CIA (*Confidentiality, Integrity, Availability*) dan antitesisnya DAD (*Disclosure, Alteration, Denial*) hingga tingkat sub-komponen.
2.  **Mendekonstruksi** sistem perangkat lunak dan infrastruktur jaringan menggunakan metodologi ancaman **STRIDE** (*Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege*).
3.  **Mengukur dan Menghitung** metrik risiko keamanan menggunakan kalkulasi matematis berbasis **CVSS v3.1** (*Common Vulnerability Scoring System*) serta estimasi finansial berbasis **FAIR** (*Factor Analysis of Information Risk*).
4.  **Mengimplementasikan** mekanisme proteksi kriptografis end-to-end (kombinasi *Authenticated Encryption with Associated Data* / AEAD dan penandatanganan digital) untuk menegakkan prinsip *Confidentiality*, *Integrity*, dan *Non-Repudiation* pada data transit.

---

### 4. The "Why" - Root Cause & First Principles

Komputasi modern dibangun di atas abstraksi efisiensi dan interoperabilitas, bukan keamanan. 
*   **Protokol Dasar Tanpa Otentikasi:** IP dirancang untuk merutekan paket tanpa memverifikasi keaslian sumber (*IP Spoofing*). DNS dibangun untuk memetakan nama ke alamat IP tanpa perlindungan kriptografis bawaan (*DNS Cache Poisoning*). BGP mengasumsikan router tetangga mengumumkan rute yang valid secara jujur (*BGP Hijacking*).
*   **Arsitektur Von Neumann:** Kode dan data berada pada ruang memori fisik yang sama. Inkonsistensi penanganan batas buffer memungkinkan data yang disuntikkan oleh adversari dieksekusi sebagai instruksi mesin (*Buffer Overflow*, *Return-Oriented Programming*).
*   **Asimetri Biaya Penyerangan (*Attacker-Defender Asymmetry*):**
    $$\text{Effort}_{\text{Defender}} \gg \text{Effort}_{\text{Attacker}}$$
    Seorang arsitek pertahanan wajib mengamankan $100\%$ permukaan serangan sepanjang waktu, sedangkan penyerang hanya perlu menemukan $1$ jalur kompromi yang valid dalam rentang waktu yang terbatas.

Tanpa model ancaman formal dan kontrol berbasis first principles, arsitektur defensif hanya bersifat reaktif—menambal gejala tanpa memperbaiki cacat fundamental pada batas kepercayaan (*trust boundary*).

---

### 5. The "What" - Deep-Dive Konsep & Mekanisme Internal

#### A. Triad CIA vs. Triad DAD
Triad CIA mendefinisikan pilar keamanan informasi klasik. Setiap pilar memiliki antitesis destruktif langsung yang disebut Triad DAD:

1.  **Confidentiality (Kerahasiaan) $\leftrightarrow$ Disclosure (Pengungkapan):**
    Akses ke informasi hanya diberikan kepada entitas terotorisasi. Kegagalan privasi menghasilkan pembocoran data sensitif (*exfiltration*). Kontrol pertahanan: Kriptografi simetris/asimetris, skema enkapsulasi kunci (*Key Encapsulation Mechanism* / KEM), *Access Control Lists* (ACL), isolasi memori kernel melalui KPTI (*Kernel Page Table Isolation*).
2.  **Integrity (Integritas) $\leftrightarrow$ Alteration (Perubahan Tanpa Izin):**
    Jaminan bahwa data, instruksi komputasi, dan state sistem tidak dimodifikasi secara ilegal oleh pihak luar atau kegagalan transmisi. Kontrol pertahanan: *Cryptographic Hash Functions* (SHA-3, BLAKE3), *Hashed Message Authentication Code* (HMAC), *Authenticated Encryption* (AES-GCM, ChaCha20-Poly1305), struktur *Merkle Trees*.
3.  **Availability (Ketersediaan) $\leftrightarrow$ Denial (Penolakan Layanan):**
    Kemampuan sistem untuk memberikan akses fungsional yang dapat diprediksi saat diminta oleh entitas terotorisasi. Kontrol pertahanan: Desain arsitektur *High Availability* (HA), proteksi mitigasi DDoS (Anycast scrubbing, eBPF/XDP rate-limiting), arsitektur *stateless worker*, *circuit breakers*.

```
   [ CIA TRIAD ]                         [ DAD TRIAD ]
   +-------------------+                 +-------------------+
   | Confidentiality   | <=============> | Disclosure        |
   +-------------------+   Destruction   +-------------------+
   | Integrity         | <=============> | Alteration        |
   +-------------------+   Destruction   +-------------------+
   | Availability      | <=============> | Denial            |
   +-------------------+                 +-------------------+
```

#### B. Parkersian Hexad (Ekspansi CIA)
Donn B. Parker mengidentifikasi keterbatasan model CIA dan memperluasnya menjadi enam pilar untuk menangani celah kontrol:
*   **Possession/Control:** Kehilangan kendali fisik atas media penyimpanan terenkripsi tidak melanggar *Confidentiality* (karena data tidak dapat didekripsi), tetapi melanggar *Possession*.
*   **Authenticity:** Validasi keaslian atribusi pengirim/pembuat data (menghindari peniruan identitas).
*   **Utility:** Kemudahan penggunaan dan bentuk data yang fungsional. Data terenkripsi yang kuncinya hilang tidak mengalami pelanggaran integritas atau kerahasiaan, melainkan hilangnya *Utility*.

#### C. Kerangka Ancaman STRIDE (Microsoft Lifecycle)
STRIDE membedah ancaman struktural terhadap komponen sistem perangkat lunak:

| Ancaman STRIDE | Definisi Vektor | Pelanggaran Pilar | Mekanisme Pertahanan Kanonikal |
| :--- | :--- | :--- | :--- |
| **S**poofing | Meniru entitas lain (IP, user, process, token) | Authenticity | Otentikasi Kriptografis (mTLS, Ed25519, FIDO2/WebAuthn) |
| **T**ampering | Memodifikasi payload data atau binary sistem | Integrity | Hashing, Signature Digital, Read-Only Filesystems, Memory Sealing |
| **R**epudiation | Menyangkal tindakan yang telah dilakukan | Non-Repudiation | Append-Only Cryptographic Audit Logs, HSM Timestamps |
| **I**nformation Disclosure | Paparan data ke pihak yang tidak berwenang | Confidentiality | Enkripsi Rest & Transit, Zeroize Memory, DLP (*Data Loss Prevention*) |
| **D**enial of Service | Menghabiskan sumber daya komputasi/jaringan | Availability | Rate Limiting (Token Bucket), SYN Cookies, eBPF Filtering, Autoscaling |
| **E**levation of Privilege | Mengeksekusi instruksi di atas privilege aslinya | Authorization | Seccomp, Linux Capabilities, AppArmor, Dropping Root Privileges |

---

### 6. Taksonomi & Variasi

```
Taksonomi Keamanan Siber
├── Model Pelaku Ancaman (Threat Actors)
│   ├── Script Kiddies / Opportunistic (Automated, uncoordinated, non-targeted)
│   ├── Cybercrime Syndicates (Financially motivated, ransomware, double-extortion)
│   ├── Advanced Persistent Threats / APT (Nation-state, highly targeted, zero-day rich)
│   └── Insiders (Malicious/negligent authorized entities)
├── Kategori Kontrol Pengamanan (Security Controls)
│   ├── Fungsional:
│   │   ├── Preventive (Mencegah eksekusi eksploitasi, e.g., IPS, memory tagging)
│   │   ├── Detective (Mendeteksi anomali/pelanggaran, e.g., SIEM, EDR, IDS)
│   │   ├── Corrective (Memulihkan status sistem, e.g., Backups, Automated Snapshots)
│   │   └── Compensating (Mitigasi alternatif saat kontrol utama tidak memungkinkan)
│   └── Implementasi:
│       ├── Administratif / Manajerial (Kebijakan, SOP, Security Clearances)
│       ├── Operasional / Prosedural (Incident response drills, patching cycle)
│       └── Teknis / Logis (Cryptographic guards, network firewalls, microsegmentation)
```

---

### 7. Bedah Arsitektur & Data Flow

Diagram di bawah menggambarkan arsitektur mikroservis aman dengan pemetaan batas kepercayaan (*trust boundary crossings*) dan titik potensi ancaman STRIDE:

```
                  [ PUBLIC / UNTRUSTED INTERNET ]
                                 │
                                 │ HTTPS / TLS 1.3 Request
                                 ▼
+ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
: INGRESS TRUST BOUNDARY                                                          :
:   +─────────────────────────────────────────────────────────────────────────+   :
:   │ API Gateway & TLS Termination (Reverse Proxy)                           │   :
:   │ [STRIDE: S, D] -> Mitigasi: mTLS, Strict ALPN, WAF Core Rule Set       │   :
:   +────────────────────────────────────┬────────────────────────────────────+   :
+ - - - - - - - - - - - - - - - - - - - -│- - - - - - - - - - - - - - - - - - - - +
                                         │ Internal RPC (Encrypted & Signed)
                                         ▼
+ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
: ZERO-TRUST INTERNAL BOUNDARY           │                                        :
:   +────────────────────────────────────┴────────────────────────────────────+   :
:   │ Service Bus / Application Logic Service                                 │   :
:   │ Context: Run as Non-Root, Dropped Linux Capabilities                    │   :
:   │ [STRIDE: T, E] -> Mitigasi: Memory-safe parsing, seccomp filters        │   :
:   +─────────────────┬──────────────────────────────────────┬────────────────+   :
:                     │                                      │                    :
:      Database Query │ Mutating Write         Audit Record  │ Tamper-Evident     :
:                     ▼                                      ▼                    :
:   +─────────────────────────────────+    +──────────────────────────────────+   :
:   │ Database System (At-Rest Crypt) │    │ Immutable Audit Log Engine       │   :
:   │ [STRIDE: I, T]                  │    │ [STRIDE: R]                      │   :
:   │ Mitigasi: AES-256-XTS           │    │ Mitigasi: Append-Only Merkle Log │   :
:   +─────────────────────────────────+    +──────────────────────────────────+   :
+ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
```

#### Alur Eksekusi Paket & Titik Validasi:
1.  **Ingress Inspection:** Paket L4-L7 tiba di Gateway; otentikasi sertifikat via mTLS (Mencegah *Spoofing*).
2.  **Rate Limiting & Scrubbing:** State filter memeriksa volume per identitas klien; mitigasi exhaustion buffer (Mencegah *Denial of Service*).
3.  **Boundary Crossing Deserialization:** Payload divalidasi terhadap skema kanonikal biner yang ketat tanpa eksekusi dinamis (Mencegah *Tampering*).
4.  **Service-to-Service Authorization:** Token berumur pendek (*short-lived cryptographic assertions*) dievaluasi per transaksi individual (Mencegah *Elevation of Privilege*).
5.  **Audit Ledger Commit:** Hash kriptografis dari operasi dimasukkan ke dalam rantai audit immutable sebelum eksekusi mutasi disk (Mencegah *Repudiation*).

---

### 8. Minimal Viable Example (MVE) - Otentikasi dan Integritas Kriptografis

Berikut adalah demonstrasi Minimal Viable Example dalam Python murni (menggunakan pustaka standar) yang menunjukkan bagaimana melindungi integritas dan non-repudiasi sebuah pesan melintasi batas kepercayaan, mencegah manipulasi payload (*Tampering*) dan pemalsuan identitas (*Spoofing*).

```python
#!/usr/bin/env python3
"""
MVE: Integritas dan Otentikasi Payload Menggunakan HMAC-SHA256.
Mendemonstrasikan pencegahan serangan Tampering dan Spoofing.
"""

import hmac
import hashlib
import json
import time

SHARED_SECRET_KEY = b"k9F#2mP$vL8*zY1@qW5!eR7^tU3&iO0("

def create_secure_payload(data: dict) -> bytes:
    """Membungkus data dengan timestamp dan signature HMAC deterministik."""
    envelope = {
        "timestamp": int(time.time()),
        "payload": data
    }
    serialized = json.dumps(envelope, sort_keys=True).encode('utf-8')
    signature = hmac.new(SHARED_SECRET_KEY, serialized, hashlib.sha256).hexdigest()
    
    # Transmit payload bersama signature
    transmission_packet = {
        "envelope": envelope,
        "signature": signature
    }
    return json.dumps(transmission_packet).encode('utf-8')

def verify_and_parse_payload(packet_bytes: bytes, max_clock_skew: int = 5) -> dict:
    """Memverifikasi signature secara konstan waktu dan memeriksa replay attack."""
    packet = json.loads(packet_bytes.decode('utf-8'))
    received_envelope = packet["envelope"]
    received_signature = packet["signature"]
    
    # Rekonstruksi serialisasi untuk validasi
    serialized = json.dumps(received_envelope, sort_keys=True).encode('utf-8')
    expected_signature = hmac.new(SHARED_SECRET_KEY, serialized, hashlib.sha256).hexdigest()
    
    # Validasi konstan waktu (mencegah timing attack)
    if not hmac.compare_digest(received_signature, expected_signature):
        raise ValueError("CRITICAL SECURITY ERROR: Integritas paket rusak atau signature tidak valid (Tampering detected)!")
        
    # Validasi batas kadaluwarsa (Mitigasi Replay Attack sederhana)
    now = int(time.time())
    if abs(now - received_envelope["timestamp"]) > max_clock_skew:
        raise ValueError("CRITICAL SECURITY ERROR: Paket kadaluwarsa atau replay attack terdeteksi!")
        
    return received_envelope["payload"]

if __name__ == "__main__":
    # 1. Aliran Normal
    raw_tx = {"from": "Alice", "to": "Bob", "amount": 1000}
    wire_data = create_secure_payload(raw_tx)
    print(f"[+] Paket Sah Terkirim: {wire_data.decode()}")
    
    verified = verify_and_parse_payload(wire_data)
    print(f"[+] Verifikasi Berhasil. Data: {verified}")
    
    # 2. Simulasi Serangan Tampering (Pihak ketiga mengubah nominal)
    tampered_packet = json.loads(wire_data.decode())
    tampered_packet["envelope"]["payload"]["amount"] = 999999  # Manipulasi data
    malicious_wire_data = json.dumps(tampered_packet).encode('utf-8')
    
    print("\n[-] Mencoba memproses paket hasil modifikasi penyerang...")
    try:
        verify_and_parse_payload(malicious_wire_data)
    except ValueError as e:
        print(f"[!] Serangan berhasil digagalkan: {e}")
```

---

### 9. Production-Grade Implementation: STRIDE-Hardened Security Envelope

Di dunia nyata, penggunaan shared-secret tunggal tidak memadai untuk sistem berkinerja tinggi yang membutuhkan enkripsi data sensitif (*Confidentiality*), perlindungan integritas (*Integrity*), dan penanganan non-repudiasi (*Authenticity*). Implementasi berikut menggunakan **AES-256-GCM** (Authenticated Encryption with Associated Data / AEAD) dengan struktur memori aman, penanganan entropy acak, dan metadata audit terikat.

```python
#!/usr/bin/env python3
"""
Production-Grade Cryptographic Security Envelope Engine
Menerapkan perlindungan CIA Triad penuh pada data in-transit/at-rest.
Dependensi: cryptography >= 41.0.0
"""

from __future__ import annotations
import os
import time
import json
import base64
import struct
from dataclasses import dataclass
from typing import Final, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

# Definisi Konstanta Keamanan Kriptografis
NONCE_BYTE_LENGTH: Final[int] = 12   # Standar NIST SP 800-38D untuk AES-GCM
KEY_BYTE_LENGTH: Final[int] = 32     # AES-256
MAX_ALLOWED_TIME_SKEW_SEC: Final[int] = 60

class SecurityEngineeringError(Exception):
    """Base exception untuk pelanggaran kontrol keamanan sistem."""
    pass

class IntegrityViolationError(SecurityEngineeringError):
    """Payload terindikasi mengalami tampering atau kerusakan bit."""
    pass

class AuthenticationReplayError(SecurityEngineeringError):
    """Indikasi serangan pemutaran ulang (replay attack) atau desinkronisasi clock."""
    pass

@dataclass(frozen=True)
class DecryptedMessage:
    payload: bytes
    sender_id: str
    timestamp_ns: int

class SecureEnvelopeEngine:
    def __init__(self, primary_key: bytes, key_identifier: str):
        if len(primary_key) != KEY_BYTE_LENGTH:
            raise ValueError(f"Ukuran kunci enkripsi wajib {KEY_BYTE_LENGTH} bytes.")
        self._key = primary_key
        self._key_id = key_identifier
        self._cipher = AESGCM(self._key)

    def seal(self, plaintext: bytes, sender_id: str) -> bytes:
        """
        Mengenkripsi dan menandatangani payload (Confidentiality + Integrity + Authenticity).
        Struktur Biner Transmisi:
        [1 Byte Version] + [2 Bytes KeyID Length] + [KeyID] + [12 Bytes Nonce] +
        [8 Bytes Timestamp NS] + [4 Bytes SenderID Length] + [SenderID] +
        [4 Bytes Ciphertext Length] + [Ciphertext + AuthTag (16 Bytes)]
        """
        if not plaintext:
            raise ValueError("Plaintext tidak boleh kosong.")
            
        # Alokasi Cryptographically Secure Pseudorandom Number Generator (CSPRNG)
        nonce = os.urandom(NONCE_BYTE_LENGTH)
        timestamp_ns = time.time_ns()
        
        # Susun Associated Authenticated Data (AAD)
        # Data ini TIDAK dienkripsi, tetapi dilindungi dari Tampering oleh Tag GCM.
        sender_bytes = sender_id.encode('utf-8')
        key_id_bytes = self._key_id.encode('utf-8')
        
        aad = struct.pack(
            f">H{len(key_id_bytes)}sQ I{len(sender_bytes)}s",
            len(key_id_bytes),
            key_id_bytes,
            timestamp_ns,
            len(sender_bytes),
            sender_bytes
        )

        # Enkripsi & Tag Generation
        ciphertext = self._cipher.encrypt(nonce, plaintext, aad)

        # Serialisasi Biner Ketat
        envelope = bytearray()
        envelope.append(0x01) # Protocol Version 1
        envelope.extend(struct.pack(">H", len(key_id_bytes)))
        envelope.extend(key_id_bytes)
        envelope.extend(nonce)
        envelope.extend(struct.pack(">Q", timestamp_ns))
        envelope.extend(struct.pack(">I", len(sender_bytes)))
        envelope.extend(sender_bytes)
        envelope.extend(struct.pack(">I", len(ciphertext)))
        envelope.extend(ciphertext)
        
        return bytes(envelope)

    def unseal(self, encrypted_envelope: bytes) -> DecryptedMessage:
        """
        Membongkar envelope biner, memvalidasi integritas AAD, dan mendekripsi ciphertext.
        """
        if len(encrypted_envelope) < (1 + 2 + NONCE_BYTE_LENGTH + 8 + 4 + 4 + 16):
            raise IntegrityViolationError("Struktur envelope biner terpotong / korup.")

        cursor = 0
        version = encrypted_envelope[cursor]
        cursor += 1
        
        if version != 0x01:
            raise SecurityEngineeringError(f"Protokol versi tidak dikenal: {version}")

        # Parsing Key Identifier
        key_id_len = struct.unpack(">H", encrypted_envelope[cursor:cursor+2])[0]
        cursor += 2
        key_id = encrypted_envelope[cursor:cursor+key_id_len].decode('utf-8')
        cursor += key_id_len

        if key_id != self._key_id:
            raise SecurityEngineeringError(f"Key mismatch: Data dienkripsi dengan ID '{key_id}'")

        # Parsing Nonce
        nonce = encrypted_envelope[cursor:cursor+NONCE_BYTE_LENGTH]
        cursor += NONCE_BYTE_LENGTH

        # Parsing Timestamp
        timestamp_ns = struct.unpack(">Q", encrypted_envelope[cursor:cursor+8])[0]
        cursor += 8

        # Validasi Temporal Anti-Replay
        now_ns = time.time_ns()
        skew_sec = abs(now_ns - timestamp_ns) / 1e9
        if skew_sec > MAX_ALLOWED_TIME_SKEW_SEC:
            raise AuthenticationReplayError(
                f"Clock skew melebihi ambang batas aman: {skew_sec:.2f}s > {MAX_ALLOWED_TIME_SKEW_SEC}s"
            )

        # Parsing Sender ID
        sender_id_len = struct.unpack(">I", encrypted_envelope[cursor:cursor+4])[0]
        cursor += 4
        sender_id = encrypted_envelope[cursor:cursor+sender_id_len].decode('utf-8')
        cursor += sender_id_len

        # Parsing Ciphertext
        ciphertext_len = struct.unpack(">I", encrypted_envelope[cursor:cursor+4])[0]
        cursor += 4
        ciphertext = encrypted_envelope[cursor:cursor+ciphertext_len]
        cursor += ciphertext_len

        if len(encrypted_envelope) != cursor:
            raise IntegrityViolationError("Trailing garbage bytes terdeteksi pada frame envelope.")

        # Rekonstruksi AAD
        sender_bytes = sender_id.encode('utf-8')
        key_id_bytes = self._key_id.encode('utf-8')
        aad = struct.pack(
            f">H{len(key_id_bytes)}sQ I{len(sender_bytes)}s",
            len(key_id_bytes),
            key_id_bytes,
            timestamp_ns,
            len(sender_bytes),
            sender_bytes
        )

        try:
            # Operasi Dekripsi sekaligus Verifikasi Autentikasi Tag
            plaintext = self._cipher.decrypt(nonce, ciphertext, aad)
        except InvalidTag:
            raise IntegrityViolationError(
                "CRITICAL SECURITY ALERT: Otentikasi GCM gagal! Ciphertext atau AAD telah dimanipulasi!"
            )

        return DecryptedMessage(
            payload=plaintext,
            sender_id=sender_id,
            timestamp_ns=timestamp_ns
        )

# Integrasi Eksekusi & Validasi Operasional
if __name__ == "__main__":
    # Inisialisasi Master Key dari Hardware Security Module (HSM) simulasi
    hsm_key = AESGCM.generate_key(bit_length=256)
    active_key_id = "kms-ap-southeast-1-key-prod-001"
    
    engine = SecureEnvelopeEngine(primary_key=hsm_key, key_identifier=active_key_id)

    # 1. Payload Transaksi Keuangan yang Sangat Sensitif
    critical_data = json.dumps({
        "order_id": "902d1847-f377-4b68-b7db-6f5df5bfb418",
        "action": "EXECUTE_CREDIT_SETTLEMENT",
        "clearing_account": "00192837461928",
        "amount_usd": "2500000.00"
    }).encode('utf-8')

    print(f"[*] Plaintext Asli ({len(critical_data)} bytes): {critical_data.decode()}")

    # 2. Penyegelan Data melintasi Batas Jaringan Tidak Aman
    sealed_wire_packet = engine.seal(plaintext=critical_data, sender_id="auth-microservice-node-03")
    print(f"[+] Ukuran Paket Biner Terisolasi: {len(sealed_wire_packet)} bytes")
    print(f"[+] Wire Representation (Base64 Preview): {base64.b64encode(sealed_wire_packet[:48]).decode()}...")

    # 3. Penerimaan Data & Pembukaan Segel pada Node Target
    decrypted_obj = engine.unseal(sealed_wire_packet)
    print(f"[+] Pembongkaran Sukses. Otentikasi Pengirim: {decrypted_obj.sender_id}")
    print(f"[+] Timestamp Terverifikasi (Epoch NS): {decrypted_obj.timestamp_ns}")
    print(f"[+] Payload Dipulihkan: {decrypted_obj.payload.decode()}")

    # 4. Validasi Keamanan: Serangan Manipulasi Byte (Bit-Flip Attack pada Ciphertext)
    print("\n[-] Skenario Serangan: Adversari membalikkan 1 bit pada ciphertext di jaringan...")
    corrupted_packet = bytearray(sealed_wire_packet)
    # Targetkan byte terakhir dari ciphertext (bagian tag otentikasi)
    corrupted_packet[-1] ^= 0xFF 
    
    try:
        engine.unseal(bytes(corrupted_packet))
    except IntegrityViolationError as err:
        print(f"[!] Sukses Mitigasi Serangan: {err}")
```

---

### 10. Edge Cases, Failure Modes, & Anti-Patterns

| Anti-Pattern / Edge Case | Mekanisme Kegagalan | Dampak Keamanan (STRIDE) | Mitigasi Wajib Tingkat Arsitektur |
| :--- | :--- | :--- | :--- |
| **AES-GCM Nonce Reuse** | Mengenkripsi dua pesan berbeda dengan $(Key, Nonce)$ yang identik pada counter-mode. | **Information Disclosure, Tampering** (Pemulihan Galois Hash Key $H$, pemalsuan total pesan berikutnya). | Gunakan format nonce deterministik berbasis counter unik, atau gunakan algoritma nonce-misuse resistant seperti **AES-GCM-SIV** (RFC 8452). |
| **MAC-then-Encrypt** | Menghitung MAC dari plaintext terlebih dahulu, lalu mengenkripsi seluruhnya. | **Information Disclosure** (Rentan terhadap serangan *Padding Oracle*, e.g., Lucky Thirteen). | Selalu terapkan **Encrypt-then-MAC** atau langsung gunakan konstruksi AEAD modern (AES-GCM, ChaCha20-Poly1305). |
| **Insecure Deserialization on Boundaries** | Mengurai objek bahasa asli (Python `pickle`, Java serialized, PHP serialize) dari entitas eksternal. | **Elevation of Privilege** (Remote Code Execution melalui eksekusi konstruktor atau gadget chains). | Gunakan format serialisasi data-only strictly typed (JSON, Protocol Buffers, FlatBuffers) tanpa instansiasi tipe dinamis. |
| **Unchecked Clock Skew (Replay Failure)** | Pengecekan timestamp mengasumsikan NTP server lokal selalu akurat secara sempurna. | **Denial of Service** (Penolakan transaksi legal jika clock melenceng) atau **Replay Attack**. | Terapkan monotonic sequence numbers bersamaan dengan time windows; sinkronisasi NTP redundan dengan bounded drift limits. |
| **Timing Non-Constant String Compare** | Memverifikasi HMAC atau password hash menggunakan pembanding bawaan bahasa (`==` atau `strcmp`). | **Information Disclosure, Spoofing** (Eksfiltrasi hash karakter demi karakter melalui latensi respon CPU). | Gunakan pembanding biner konstan-waktu (*constant-time comparison*), misal: `CRYPTO_memcmp` di C atau `hmac.compare_digest` di Python. |

---

### 11. Trade-Off Analysis: Security vs. Performance vs. Usability

Dalam rekayasa sistem riil, arsitek keamanan wajib mengevaluasi implikasi trade-off arsitektural:

```
                  [ Keamanan Maksimal ]
                  (Zero Trust, HSM, KMS,
                   AEAD, Per-Request mTLS)
                           /\
                          /  \
                         /    \
                        /      \
                       /   ▲    \
                      /    │     \
                     /  Keseimbangan
                    /  Rekayasa   \
                   /       ▼       \
                  /                 \
  [ Performa Tinggi ] ────────────── [ Kemudahan Penggunaan ]
 (No Handshake, Raw                  (Single Sign-On Statis,
  TCP, Non-Encrypted                   Hardcoded Secrets,
  IPC, Memory Direct)                  Open Network Ports)
```

#### Matriks Evaluasi Parameter:
1.  **Enkripsi Penuh Transmisi Jaringan (mTLS End-to-End) vs. Ingress Termination:**
    *   *Trade-off:* mTLS internal mengeliminasi risiko pembajakan lateral network (*packet sniffing* oleh rogue container), namun memperkenalkan beban komputasi CPU sebesar $15\text{--}25\%$ pada pemrosesan handshake L7 dan mempersulit observabilitas packet-capture (PCAP).
    *   *Keputusan Desain:* Gunakan mTLS dengan sesi TLS 1.3 resumption tickets, serta hardware acceleration untuk instruksi AES-NI pada host ingress.
2.  **Stateful Replay Cache vs. Stateless Ephemeral Tokens:**
    *   *Trade-off:* Stateful memory tracking (misal: Redis distributed set untuk melacak semua ID transaksi yang pernah diproses) sepenuhnya menutup celah replay attacks, tetapi menjadi single point of failure (SPOF) dan memperkenalkan latensi $\mathcal{O}(1)$ IO network round-trip. Stateless timestamps rentan terhadap serangan di dalam celah sempit *clock skew window*.
    *   *Keputusan Desain:* Terapkan skema hibrida; stateless TTL short window (misal: $30$ detik) dipadukan dengan Bloom Filter lokal di setiap node mikroservis untuk melacak ID transaksi dalam window tersebut tanpa dependensi jaringan terpusat.

---

### 12. Pertimbangan Skala, Performa, & Throughput

Saat mengamankan sistem berskala petabyte atau berkecepatan lebih dari 100.000 Request Per Second (RPS), kontrol keamanan konvensional dapat menimbulkan degradasi throughput:

1.  **Overhead Algoritma Kriptografi pada Throughput:**
    *   Enkripsi perangkat lunak konvensional dapat membebani CPU. Pada arsitektur modern (x86_64), AES-GCM memanfaatkan instruksi hardware dedicated (`AES-NI` dan `PCLMULQDQ`).
    *   Jika hardware target tidak memiliki modul akselerasi kriptografi AES hardware (misal: IoT atau node ARM versi lama), **ChaCha20-Poly1305** beroperasi secara konsisten lebih cepat dan deterministik tanpa risiko *cache-timing vulnerabilities*.
2.  **Optimasi Alokasi Memori Biner:**
    *   Penggunaan pembungkus JSON/Base64 untuk memindahkan data terenkripsi meningkatkan overhead payload sebesar $\approx 33\%$.
    *   Pada throughput tinggi, gunakan struktur binary-packed (`struct` di C/Python, atau protobuf bytes) untuk meminimalkan alokasi garbage collection dan menjaga utilisasi memory buffer tetap dalam batas efisiensi cache L1/L2 CPU.
3.  **Karakteristik Kompleksitas Waktu dan Ruang:**
    *   *AES-GCM Encryption / Decryption:* Waktu $\mathcal{O}(N)$ terhadap panjang payload, Ruang $\mathcal{O}(1)$ memory overhead pada streaming mode.
    *   *Verification of Constant-Time MAC:* Waktu $\mathcal{O}(L)$ konstan independen dari lokasi kegagalan byte (di mana $L$ adalah panjang digest).

---

### 13. Keamanan, Observabilitas, & Auditability

Sistem defensif yang handal wajib menyediakan visibilitas forensik deterministik tanpa membocorkan data rahasia (*telemetry leakage*).

#### Telemetri & Structured Audit Log Format
Setiap penolakan kontrol keamanan wajib mencatat detail forensik struktural (JSON format) ke sistem log yang bersifat *immutable* dan *append-only*:

```json
{
  "event_id": "c1f7b6b0-7e4b-4c28-86d7-84a86b3e8e12",
  "timestamp_iso": "2026-03-31T03:59:02.128374Z",
  "actor": {
    "sender_id": "auth-microservice-node-03",
    "source_ip": "10.244.3.45",
    "service_account": "sa-payment-processor@prod.internal"
  },
  "action": "CRYPTO_SECURITY_ENVELOPE_UNSEAL",
  "status": "SECURITY_VIOLATION",
  "violation_type": "INTEGRITY_COMPROMISE",
  "threat_mapping": {
    "framework": "STRIDE",
    "category": "TAMPERING",
    "cvss_vector": "CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N"
  },
  "metadata": {
    "key_identifier": "kms-ap-southeast-1-key-prod-001",
    "failure_reason": "AEAD_TAG_MISMATCH",
    "received_payload_size_bytes": 1048
  }
}
```

#### Metrik Operasional Keamanan (Prometheus Instrumentasi):
*   `security_enclave_integrity_failures_total{sender_id="..."}`: Counter yang melacak kegagalan verifikasi tag otentikasi. Alert P1 jika laju mutasi $\ge 1 \text{ error/detik}$.
*   `security_enclave_clock_skew_drift_seconds`: Histogram melacak perbedaan waktu antara pengirim dan penerima payload. Digunakan untuk mendeteksi drift NTP dan serangan *replay*.

---

### 14. Verifikasi, Testing, & Validasi

Berikut adalah rangkaian pengujian terotomatisasi menggunakan framework `pytest` untuk memverifikasi ketahanan kontrol kriptografis dari implementasi Section 9 terhadap berbagai skenario eksploitasi adversarial:

```python
#!/usr/bin/env python3
"""
Test Suite: Verifikasi Batas Keamanan dan Model Ancaman STRIDE.
Eksekusi via terminal: pytest -v test_security_engine.py
"""

import time
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from production_security_envelope import (
    SecureEnvelopeEngine,
    IntegrityViolationError,
    AuthenticationReplayError,
    SecurityEngineeringError
)

@pytest.fixture
def security_engine():
    key = AESGCM.generate_key(bit_length=256)
    return SecureEnvelopeEngine(primary_key=key, key_identifier="test-key-suite")

def test_happy_path_encryption_decryption(security_engine):
    """Verifikasi bahwa data valid dapat diproses tanpa kehilangan data."""
    raw_message = b"CRITICAL_TRANSACTION_PAYLOAD"
    sender = "service-unit-test"
    
    sealed = security_engine.seal(raw_message, sender)
    unsealed = security_engine.unseal(sealed)
    
    assert unsealed.payload == raw_message
    assert unsealed.sender_id == sender

def test_tampering_payload_detection(security_engine):
    """STRIDE: Tampering - Memodifikasi ciphertext wajib memicu IntegrityViolationError."""
    raw_message = b"ALLOW_USER_ID=100"
    sealed = bytearray(security_engine.seal(raw_message, "service-auth"))
    
    # Mutasikan 1 byte di payload payload area
    sealed[-5] ^= 0x42 
    
    with pytest.raises(IntegrityViolationError):
        security_engine.unseal(bytes(sealed))

def test_tampering_aad_sender_detection(security_engine):
    """STRIDE: Spoofing/Tampering - Memodifikasi Sender ID dalam transit harus ditolak oleh Tag AEAD."""
    raw_message = b"GRANT_ADMIN_RIGHTS"
    sealed = bytearray(security_engine.seal(raw_message, "node-regular"))
    
    # Letak Sender ID berada setelah Version(1) + KeyLen(2) + KeyID + Nonce(12) + Timestamp(8) + SenderLen(4)
    # Ubah data biner langsung
    target_idx = 1 + 2 + len("test-key-suite") + 12 + 8 + 4
    sealed[target_idx] = ord('x') # Ubah byte pertama sender
    
    with pytest.raises(IntegrityViolationError):
        security_engine.unseal(bytes(sealed))

def test_replay_attack_tolerance_window(security_engine):
    """STRIDE: Repudiation/Replay - Paket di luar jendela toleransi waktu wajib digagalkan."""
    raw_message = b"TRANSACTION_TRANSFER"
    
    # Segel pesan
    sealed = security_engine.seal(raw_message, "node-payment")
    
    # Simulasi pembongkaran paket dengan clock sistem masa depan yang melenceng jauh
    with pytest.MonkeyPatch.context() as m:
        # Pindahkan waktu sistem lokal 100 detik ke depan
        future_time_ns = time.time_ns() + (100 * 1_000_000_000)
        m.setattr(time, "time_ns", lambda: future_time_ns)
        
        with pytest.raises(AuthenticationReplayError):
            security_engine.unseal(sealed)

def test_truncated_binary_attack(security_engine):
    """Verifikasi penolakan sistem terhadap serangan paket biner terpotong (fuzzing boundary)."""
    with pytest.raises(IntegrityViolationError):
        security_engine.unseal(b"\x01\x00\x05junk")
```

---

### 15. Runbook Diagnostik & Mitigasi Insiden

#### Status Insiden: P1 - Indikasi Serangan Modifikasi Data Massal (Integrity Breach Alert)

```
                     +---------------------------------------+
                     | Security Alert: AEAD Tag Mismatches   |
                     | > 10 req/s detected in Log Aggregator |
                     +-------------------+-------------------+
                                         │
                                         ▼
                     +---------------------------------------+
                     | STEP 1: Identifikasi IP Sumber &      |
                     | Pod Pengirim melalui Service Mesh     |
                     +-------------------+-------------------+
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
     [ Eksternal / Ingress ]                         [ Internal Microservices ]
                 │                                               │
                 ▼                                               ▼
+─────────────────────────────────+             +─────────────────────────────────+
| STEP 2A: Terapkan mitigasi L3   |             | STEP 2B: Isolasi Pod/Node via   |
| IP Block via Edge Firewall /    |             | NetworkPolicy (Deny All Ingress)|
| Cloudflare WAF                  |             +────────────────┬────────────────+
+─────────────────────────────────+                              │
                                                                 ▼
                                                +─────────────────────────────────+
                                                | STEP 3: Dump memori proses      |
                                                | untuk ekstraksi artefak forensik|
                                                +────────────────┬────────────────+
                                                                 │
                                                                 ▼
                                                +─────────────────────────────────+
                                                | STEP 4: Putar Kunci Kriptografi |
                                                | (Automated Key Rotation via KMS)|
                                                +─────────────────────────────────+
```

#### Tindakan Diagnostik Melalui CLI:
1.  **Analisis Log Integritas:**
    ```bash
    # Filter log integrasi yang ditolak dalam 15 menit terakhir
    journalctl -u secure-envelope-service --since "15 minutes ago" | grep "INTEGRITY_COMPROMISE" | jq .
    ```
2.  **Isolasi Jaringan Cepat (Zero-Trust Quarantining):**
    ```bash
    # Mengisolasi host pengirim yang terkompromi menggunakan iptables
    sudo iptables -I INPUT 1 -s 10.244.3.45 -j DROP
    ```
3.  **Ekstraksi Memory Buffer untuk Analisis Forensik Eksploit:**
    ```bash
    # Mengambil memory core dump dari proses yang dicurigai disusupi tanpa mematikannya
    sudo gcore -o /opt/incident/process_dump_$(date +%s) $(pgrep -f secure-envelope)
    ```

---

### 16. Ringkasan Eksekutif & "Cheat Sheet"

*   **Tiga Pilar & Antitesis:**
    *   *Confidentiality* (Lawan: *Disclosure*) $\rightarrow$ Defensif: AEAD, KEM, KPTI.
    *   *Integrity* (Lawan: *Alteration*) $\rightarrow$ Defensif: SHA-3, HMAC, Tagging Kriptografis.
    *   *Availability* (Lawan: *Denial*) $\rightarrow$ Defensif: eBPF/XDP rate limiting, Stateless Workers.
*   **Pemetaan Singkat STRIDE:**
    *   **S**poofing $\rightarrow$ Gunakan Otentikasi Kuat (Mutual TLS, FIDO2).
    *   **T**ampering $\rightarrow$ Gunakan Enkripsi Terotentikasi (AES-GCM, HMAC).
    *   **R**epudiation $\rightarrow$ Gunakan Append-Only Logs, Digital Signatures.
    *   **I**nformation Disclosure $\rightarrow$ Gunakan Enkripsi Data Transit & Rest.
    *   **D**enial of Service $\rightarrow$ Gunakan Rate Limiter, Autoscaling, Timeout.
    *   **E**levation of Privilege $\rightarrow$ Terapkan Prinsip *Least Privilege*, Drop Privileges.
*   **Heuristik Keputusan Cepat Arsitektur:**
    1.  *Jangan pernah* mengimplementasikan algoritma enkripsi sendiri (*Never roll your own crypto*).
    2.  Semua parsing string biner dari media tidak aman adalah untrusted input $\rightarrow$ batasi ukuran maksimum buffer parsing sebelum decoding.
    3.  Pengecekan keamanan harus gagal secara tertutup (*Fail-Safe Defaults / Fail-Closed*).

---

### 17. Hands-On Lab Challenge: Mengamankan Pipeline Transaksi Perbankan

#### Skenario:
Sebuah sistem perbankan internal mengeksekusi instruksi debit rekening melalui soket TCP menggunakan payload JSON mentah. Sistem ini rentan terhadap serangan peniruan identitas (*Spoofing*), pengubahan saldo transaksi (*Tampering*), dan eksekusi transaksi berulang (*Replay Attack*).

#### Tugas Rekayasa Anda:
Lengkapi kelas `InsecureLedgerProcessor` di bawah ini agar memenuhi standar produksi zero-trust:
1.  Implementasikan otentikasi dan integritas payload menggunakan skema HMAC-SHA256 atau AES-GCM.
2.  Sertakan mekanisme pencegahan replay attack berbasis nonce monotonic tracker atau timestamp-window check.
3.  Wajib menolak transaksi apapun yang dimodifikasi sekecil $1$ bit pun dengan melempar pengecualian `SecurityLedgerException`.

#### Skeleton Kode Lab:

```python
#!/usr/bin/env python3
"""
LAB CHALLENGE: Refactor Ledger Pipeline Menjadi Tahan STRIDE
"""

class SecurityLedgerException(Exception):
    pass

class HardenedLedgerProcessor:
    def __init__(self, authentication_key: bytes):
        self._auth_key = authentication_key
        # TODO: Inisialisasi state tracking untuk nonce/anti-replay

    def build_transaction_packet(self, sender_acc: str, target_acc: str, amount: float) -> bytes:
        """
        TUGAS: Kemas payload transaksi ini agar aman dari modifikasi (Tampering),
        pemalsuan (Spoofing), dan replay attack.
        """
        # IMPLEMENTASIKAN DI SINI
        pass

    def process_incoming_packet(self, packet_bytes: bytes) -> dict:
        """
        TUGAS: Verifikasi integritas, non-repudiasi, otentikasi, dan waktu replay.
        Kembalikan dict {"sender": ..., "target": ..., "amount": ...} jika sah.
        Lempar SecurityLedgerException jika paket terindikasi diserang.
        """
        # IMPLEMENTASIKAN DI SINI
        pass
```

---

### 18. Solusi Lab Challenge: Hardened Ledger Pipeline

Di bawah ini adalah solusi implementasi tingkat produksi untuk tantangan Lab di atas dengan menerapkan skema *Authenticated Message Protocol* menggunakan HMAC-SHA256, Nonce Tracking, dan Validasi Monotonik:

```python
#!/usr/bin/env python3
"""
SOLUSI RESMI: Hardened Ledger Pipeline
Memenuhi seluruh parameter mitigasi STRIDE: S, T, R, D.
"""

import hmac
import hashlib
import json
import time
import uuid

class SecurityLedgerException(Exception):
    """Pengecualian spesifik kegagalan integritas ledger."""
    pass

class HardenedLedgerProcessor:
    def __init__(self, authentication_key: bytes, max_drift_seconds: int = 10):
        if len(authentication_key) < 32:
            raise ValueError("Kunci otentikasi minimal harus 32 bytes.")
        self._auth_key = authentication_key
        self._max_drift = max_drift_seconds
        # In-memory nonce cache untuk mencegah Replay Attacks
        self._processed_nonces: set[str] = set()

    def build_transaction_packet(self, sender_acc: str, target_acc: str, amount: float) -> bytes:
        """Membungkus data transaksi ke dalam format aman anti-tamper & anti-replay."""
        if amount <= 0:
            raise ValueError("Jumlah transaksi harus positif.")

        envelope = {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "payload": {
                "sender": sender_acc,
                "target": target_acc,
                "amount": float(amount)
            }
        }
        
        # Serialisasi kanonikal (kunci JSON terurut deterministik)
        serialized_envelope = json.dumps(envelope, sort_keys=True).encode('utf-8')
        
        # Generasi HMAC-SHA256
        mac = hmac.new(self._auth_key, serialized_envelope, hashlib.sha256).hexdigest()
        
        transmission = {
            "data": envelope,
            "mac": mac
        }
        return json.dumps(transmission).encode('utf-8')

    def process_incoming_packet(self, packet_bytes: bytes) -> dict:
        """Membedah, memverifikasi tanda tangan kriptografis, dan memfilter replay."""
        try:
            packet = json.loads(packet_bytes.decode('utf-8'))
            data_envelope = packet["data"]
            received_mac = packet["mac"]
        except Exception as err:
            raise SecurityLedgerException(f"Struktur paket data cacat: {err}") from err

        # 1. Verifikasi Integritas & Otentikasi (Mitigasi Tampering & Spoofing)
        canonical_serialized = json.dumps(data_envelope, sort_keys=True).encode('utf-8')
        expected_mac = hmac.new(self._auth_key, canonical_serialized, hashlib.sha256).hexdigest()
        
        # Eksekusi pembandingan konstan-waktu (Mitigasi Timing Attack)
        if not hmac.compare_digest(received_mac, expected_mac):
            raise SecurityLedgerException("SECURITY VIOLATION: Manipulasi data terdeteksi! (HMAC mismatch)")

        # 2. Verifikasi Batas Waktu Kadaluwarsa (Mitigasi Serangan Drift/Lag)
        now = time.time()
        tx_time = data_envelope.get("timestamp", 0)
        if abs(now - tx_time) > self._max_drift:
            raise SecurityLedgerException("SECURITY VIOLATION: Transaksi kadaluwarsa atau clock skew terlalu besar.")

        # 3. Pencegahan Replay Attack (Mitigasi Repudiation/Replay)
        tx_id = data_envelope.get("transaction_id")
        if not tx_id or tx_id in self._processed_nonces:
            raise SecurityLedgerException(f"SECURITY VIOLATION: Replay attack terdeteksi untuk TX: {tx_id}")

        # Catat nonce untuk mencegah pemutaran ulang transaksi di masa valid
        self._processed_nonces.add(tx_id)

        return data_envelope["payload"]

# Demonstrasi Validasi Solusi
if __name__ == "__main__":
    shared_key = b"super-secure-shared-secret-key-32bytes!!"
    processor = HardenedLedgerProcessor(authentication_key=shared_key)

    # 1. Transaksi Legal
    tx_wire = processor.build_transaction_packet("ACC-001", "ACC-002", 500.0)
    result = processor.process_incoming_packet(tx_wire)
    print(f"[+] Transaksi sukses diproses: {result}")

    # 2. Serangan Replay
    print("\n[-] Mencoba mengirim ulang paket transaksi yang sama (Replay Attack)...")
    try:
        processor.process_incoming_packet(tx_wire)
    except SecurityLedgerException as ex:
        print(f"[!] Replay digagalkan: {ex}")

    # 3. Serangan Modifikasi Saldo
    print("\n[-] Mencoba mengubah nilai uang pada paket transaksi di jaringan (Tampering)...")
    tampered_raw = json.loads(tx_wire.decode())
    tampered_raw["data"]["payload"]["amount"] = 9999999.0
    try:
        processor.process_incoming_packet(json.dumps(tampered_raw).encode())
    except SecurityLedgerException as ex:
        print(f"[!] Tampering digagalkan: {ex}")
```

---

### 19. FAQ Terkurasi (Masalah Teknis Tingkat Lanjut)

*   **Q: Kapan saya harus memilih AES-GCM dibanding ChaCha20-Poly1305?**
    *   *Jawaban Teknis:* Gunakan **AES-GCM** bila sistem target berjalan di atas arsitektur prosesor x86-64 yang memiliki instruksi perangkat keras `AES-NI`. Dalam kondisi ini, AES-GCM mampu mencapai throughput multi-gigabit per core dengan latensi sangat rendah. Gunakan **ChaCha20-Poly1305** jika target sistem berjalan pada prosesor perangkat embedded, mobile, atau arsitektur tanpa modul hardware AES; implementasi ChaCha20 di software murni kebal terhadap *cache-timing side-channel attacks* yang kerap menimpa implementasi software AES.
*   **Q: Apakah Base CVSS Score v3.1 sudah cukup mencerminkan risiko nyata sistem saya?**
    *   *Jawaban Teknis:* Tidak. Base Metric hanya mengevaluasi karakteristik bawaan dari sebuah kerentanan terisolasi. Dalam rekayasa keamanan produksi, Anda wajib mengkalkulasi **Environmental Metric** dan **Temporal Metric**. Kerentanan *Critical* (CVSS 9.8) pada layanan yang diisolasi di jaringan udara (*air-gapped*) tanpa kompilator lokal memiliki risiko riil jauh lebih rendah dibandingkan kerentanan *Medium* (CVSS 6.5) pada API perimeter publik yang menyimpan data PII (*Personally Identifiable Information*).
*   **Q: Mengapa HMAC-SHA256 kebal terhadap Length Extension Attack sedangkan SHA-256 murni rentan?**
    *   *Jawaban Teknis:* SHA-256 didasarkan pada konstruksi Merkle-Damgård di mana state internal akhir langsung dipetakan menjadi digest output. Hal ini memungkinkan penyerang menyuntikkan blok data baru di akhir payload tanpa mengetahui kunci aslinya. HMAC menyelesaikan masalah ini dengan menggunakan konstruksi bersarang ganda yang mengisolasi state internal:
    $$\text{HMAC}(K, m) = H\Big((K' \oplus \text{opad}) \mathbin{\Vert} H\big((K' \oplus \text{ipad}) \mathbin{\Vert} m\big)\Big)$$
    Digest luar $H$ mengenkapsulasi seluruh proses hashing internal, sehingga penyerang tidak dapat mengekstrapolasi state Merkle-Damgård internal untuk memperpanjang data.

---

### 20. Referensi & Rekomendasi Bacaan Lanjutan

1.  **Standar Formal & Spesifikasi Teknis:**
    *   *NIST Special Publication 800-38D:* "Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC."
    *   *RFC 8446:* "The Transport Layer Security (TLS) Protocol Version 1.3" (IETF Standards Track).
    *   *RFC 2104:* "HMAC: Keyed-Hashing for Message Authentication."
2.  **Literatur Akademik & Fundamental:**
    *   Saltzer, J. H., & Schroeder, M. D. (1975). *The Protection of Information in Computer Systems*. Proceedings of the IEEE, 63(9), 1278-1308. (Makalah seminalis perintis prinsip least privilege dan fail-safe defaults).
    *   Shostack, Adam. (2014). *Threat Modeling: Designing for Security*. John Wiley & Sons. (Buku panduan definitif metodologi STRIDE).
3.  **Dokumentasi Open-Source Terverifikasi:**
    *   *OWASP Threat Dragon & OWASP ASVS (Application Security Verification Standard) v4.0.*
    *   *Common Vulnerability Scoring System (CVSS) v3.1 Specification Guide* (FIRST.org).