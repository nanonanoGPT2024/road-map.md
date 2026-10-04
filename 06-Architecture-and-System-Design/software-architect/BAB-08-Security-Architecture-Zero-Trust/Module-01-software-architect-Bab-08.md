# Kurikulum Software Architect
## Kategori: 06-Architecture-and-System-Design
### Bab 08 — Security Architecture & Zero Trust

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `SA-CSD-0801`
* **Judul Modul**: Security Architecture & Zero Trust: Threat Modeling (STRIDE), Defense in Depth, Cryptographic Architectures, Zero-Trust Architecture, Identity & Access Management (IAM)
* **Kategori**: `06-Architecture-and-System-Design`
* **Tingkat Kesulitan**: Tingkat Lanjut (Advanced / Expert)
* **Prasyarat**: 
  * Pemahaman mendalam tentang Distributed Systems (`SA-CSD-01` s/d `04`)
  * Protokol Jaringan: TCP/IP, TLS 1.3, HTTP/2, DNS, gRPC
  * Konsep Dasar Kriptografi: Simetrik, Asimetrik, Hashing, Tanda Tangan Digital (Digital Signatures)
* **Estimasi Waktu Belajar**: 14 - 18 Jam Pembelajaran Mandiri / Workshop Terpandu
* **Target Pembaca**: Principal Architect, Enterprise Architect, Lead Security Engineer, Staff Backend Engineer

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kapabilitas untuk:

1. **Menganalisis dan Memitigasi Risiko Permukaan Serangan (Attack Surface)** menggunakan metodologi formal *STRIDE* dan *DREAD* melalui pembuatan *Threat Model* berbasis *Data Flow Diagram (DFD)* tingkat sistem.
2. **Merancang Arsitektur Zero-Trust (ZTA)** yang sepenuhnya mematuhi prinsip *NIST SP 800-207*, memisahkan *Control Plane* (*Policy Decision Point*) dan *Data Plane* (*Policy Enforcement Point*) tanpa mengandalkan perimeter jaringan implisit.
3. **Mengembangkan Pola Kriptografi Tingkat Perusahaan (Cryptographic Architectures)**, mencakup implementasi *Envelope Encryption* berbasis KMS, isolasi kunci berbasis HSM, rotasi kunci otomatis tanpa downtime, serta orkestrasinya pada transit (*mTLS*) dan rest (*AES-256-GCM / ChaCha20-Poly1305*).
4. **Membangun Model Otorisasi Lanjutan** yang mengevaluasi *Role-Based Access Control* (RBAC), *Attribute-Based Access Control* (ABAC), dan *Relationship-Based Access Control* (ReBAC / model Google Zanzibar) dengan penegakan latensi sub-milidetik.
5. **Menerapkan Paradigma Defense in Depth** melintasi 7 lapisan arsitektur (Perimeter, Network, Host, Runtime, Application, Data, Identity) untuk menjamin ketahanan terhadap intrusi persisten (Advanced Persistent Threats - APT).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [SECURITY ARCHITECTURE]
                                       |
    +------------------+---------------+---------------+------------------+
    |                  |                               |                  |
[THREAT MODELING] [DEFENSE IN DEPTH]          [ZERO-TRUST (ZTA)]       [IAM & CRYPTO]
    |                  |                               |                  |
    +-- STRIDE         +-- Perimeter (WAF/DDoS)        +-- NIST SP 800-207+-- Identity
    |   * Spoofing     +-- Network (Microsegmentation) +-- Control Plane  |   * OIDC/SAML
    |   * Tampering    +-- Host (Hardening/SELinux)    |   * Policy Engine|   * WebAuthn/FIDO2
    |   * Repudiation  +-- Runtime (AppArmor/K8s PSA)  |   * Policy Admin |   * SPIFFE/SPIRE
    |   * Info Leak    +-- Application (SAST/DAST/RASP)|   * Trust Engine +-- Access Control
    |   * Denial of S. +-- Data (Crypto Envelope)      +-- Data Plane     |   * RBAC / ABAC
    |   * Elevation    +-- Identity (MFA/Conditional)      * PEP (Envoy)  |   * ReBAC (Zanzibar)
    +-- DREAD Scoring                                  +-- Continuous Verif+-- Cryptography
    +-- Attack Trees                                                      |   * KMS / HSM
                                                                          |   * KEK & DEK
                                                                          |   * Envelope Encrypt
                                                                          |   * mTLS (TLS 1.3)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

1. **Runtuhnya Kepercayaan Perimeter (Castle-and-Moat Failure)**:
   Model keamanan tradisional mengasumsikan siapa pun yang berada di dalam jaringan privat (VPC atau intranet via VPN) adalah entitas terpercaya. Paradigma ini telah gagal total. Pelanggaran data skala besar kontemporer (seperti *SolarWinds*, *Equifax*, dan serangan rantai pasok modern) membuktikan bahwa setelah penyerang menembus perimeter, mereka dapat bergerak lateral (*lateral movement*) tanpa hambatan. Zero Trust berasumsi bahwa kompromi telah terjadi (*assume breach*).

2. **Dampak Finansial, Regulasi, dan Eksistensial**:
   Berdasarkan laporan *Cost of a Data Breach* tahunan oleh IBM/Ponemon Institute, biaya rata-rata pelanggaran data melampaui USD 4,45 juta. Regulasi global dan domestik (seperti UU Perlindungan Data Pribadi / PDP di Indonesia, GDPR di Eropa, HIPAA, PCI-DSS 4.0) menuntut sanksi denda berbasis persentase pendapatan tahunan dan pertanggungjawaban pidana atas kegagalan perancangan privasi (*Privacy by Design*).

3. **Pergeseran Arsitektur Modern**:
   Transisi menuju *Microservices*, *Multi-Cloud*, *Edge Computing*, dan pekerja remote terdistribusi menghancurkan batas fisik data center. Keamanan tidak lagi dapat diisolasi pada firewall perbatasan; identitas entitas (manusia, service, mesin) dan kriptografi harus menjadi batas keamanan (*security perimeter*) yang baru.

4. **Biaya Remediasi yang Bersifat Eksponensial**:
   Memperbaiki kerentanan arsitektural pada fase produksi memakan biaya hingga 100 kali lipat lebih besar dibanding merancangnya secara benar pada fase desain (*Threat Modeling*). Kegagalan kriptografi dan otorisasi tidak dapat diselesaikan hanya dengan patching paket; kegagalan tersebut menuntut redesain struktural sistem.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Threat Modeling (STRIDE)
Threat modeling adalah proses terstruktur untuk mengidentifikasi, mengkuantifikasi, dan memitigasi risiko keamanan serta kerentanan arsitektur sebelum sebaris kode pun dieksekusi. Framework **STRIDE** (dikembangkan oleh Praerit Garg dan Loren Kohnfelder di Microsoft) mengklasifikasikan ancaman menjadi enam kategori:
* **Spoofing**: Penyamaran identitas entitas (aktor atau sistem). Solusi: Autentikasi kuat (*strong authentication*).
* **Tampering**: Modifikasi data tanpa izin, baik pada media penyimpanan maupun transit. Solusi: Integritas kriptografis, hashing, tanda tangan digital.
* **Repudiation**: Penyangkalan atas suatu aksi yang dilakukan. Solusi: *Non-repudiation*, audit trail terenkripsi dan append-only.
* **Information Disclosure**: Bocornya data sensitif ke pihak yang tidak berhak. Solusi: Enkripsi data, *data masking*, kontrol akses ketat.
* **Denial of Service (DoS)**: Penurunan performa atau pemadaman ketersediaan sistem. Solusi: *Rate limiting*, elastisitas arsitektur, isolasi resource.
* **Elevation of Privilege**: Perolehan hak akses melebihi batas legalitas. Solusi: Otorisasi berbasis hak akses terendah (*Least Privilege*).

### 2. Defense in Depth
Konsep keamanan berlapis di mana kegagalan pada satu kontrol pertahanan tidak langsung menyebabkan kompromi sistem secara keseluruhan. Lapisan-lapisan ini mencakup:
* **Perimeter Layer**: DDoS Protection, WAF, CDN Edge filtering.
* **Network Layer**: Microsegmentation, VPC peering boundaries, isolated subnets, firewall stateful/stateless.
* **Compute/Host Layer**: Hardening OS (CIS Benchmarks), Minimal Base Images (Distroless), SELinux/AppArmor.
* **Runtime Layer**: Container Sandboxing (gVisor, Kata Containers), Kubernetes Pod Security Standards (PSS/PSA).
* **Application Layer**: Validasi input, dependency scanning (SCA), SAST/DAST, memory-safe languages.
* **Data Layer**: Enkripsi rest/transit/use, data anonymization, tokenization.
* **Identity Layer**: MFA, zero-trust token exchange, device posture checks.

### 3. Cryptographic Architectures
Bukan sekadar memanggil library enkripsi, arsitektur kriptografi mencakup perancangan manajemen siklus hidup kunci (*key lifecycle management*), hierarki kunci, dan pembagian tanggung jawab proteksi data.
* **Envelope Encryption**: Teknik mengenkripsi *plaintext* menggunakan kunci simetris sekali pakai yang unik (*Data Encryption Key* / DEK), kemudian mengenkripsi DEK tersebut menggunakan kunci utama (*Key Encryption Key* / KEK) yang berada di dalam *Hardware Security Module* (HSM) atau *Key Management Service* (KMS).
* **Cryptographic Agility**: Kemampuan arsitektur untuk mengganti algoritma kriptografi (misal: migrasi dari RSA ke ECDSA atau Post-Quantum Cryptography/ML-KEM) tanpa merusak skema penyimpanan atau menghentikan sistem.

### 4. Zero-Trust Architecture (ZTA — NIST SP 800-207)
ZTA adalah model arsitektur keamanan yang meniadakan konsep kepercayaan implisit berdasarkan lokasi fisik maupun jaringan. ZTA berlandaskan tiga postulat utama:
1. **Never Trust, Always Verify**: Autentikasi dan otorisasi secara eksplisit untuk setiap permintaan akses, secara terus-menerus (*continuous assessment*).
2. **Assume Breach**: Beroperasi dengan asumsi bahwa musuh sudah berada di dalam sistem; minimalkan *blast radius* melalui segmentasi mikro.
3. **Verify Explicitly**: Keputusan akses dibuat secara dinamis menggunakan seluruh sinyal data yang tersedia (identitas pengguna, lokasi, postur perangkat, konteks beban kerja, anomali data).

Komponen inti ZTA:
* **Control Plane**: Terdiri dari **Policy Engine (PE)** (otak penentu keputusan) dan **Policy Administrator (PA)** (pemberi instruksi pembukaan kanal koneksi). Bersama-sama keduanya disebut **Policy Decision Point (PDP)**.
* **Data Plane**: Terdiri dari **Policy Enforcement Point (PEP)** (proksi/gateway yang mencegat, memeriksa, dan memutus koneksi berdasarkan instruksi PDP).

### 5. Identity & Access Management (IAM)
Fondasi ZTA yang mengatur identitas entitas dan kontrol akses:
* **Autentikasi (AuthN)**: OIDC (OpenID Connect), OAuth 2.0 (RFC 6749, RFC 7636 PKCE), WebAuthn (FIDO2 passkeys), SPIFFE/SPIRE untuk identitas dinamis beban kerja (*workload identity*).
* **Model Otorisasi (AuthZ)**:
  * **RBAC (Role-Based)**: Izin diikat pada peran statis (`Role -> Permission`).
  * **ABAC (Attribute-Based)**: Izin dihitung secara dinamis berbasis atribut subjek, objek, aksi, dan lingkungan (`f(Subject, Object, Action, Environment) -> Allow/Deny`).
  * **ReBAC (Relationship-Based)**: Izin didasarkan pada grafik relasi antar-objek (contoh: model Google Zanzibar: *User X can edit Document Y because X is member of Team Z which owns Folder W which contains Document Y*).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### 1. Metodologi Threat Modeling Sistemik
Threat modeling dilakukan melalui 4 langkah siklis:
1. **Dekomposisi Sistem (Deconstruct)**: Menggambar *Data Flow Diagram (DFD)* tingkat lanjut dengan batas kepercayaan yang jelas (*Trust Boundaries*). Trust boundary memisahkan entitas dengan tingkat hak akses atau kepemilikan yang berbeda (contoh: Internet publik vs Reverse Proxy, DMZ vs Internal Microservices, Worker Node vs Database).
2. **Identifikasi Ancaman (Categorize)**: Menerapkan matriks STRIDE pada setiap elemen DFD:
   * *External Entity*: Spoofing, Repudiation.
   * *Data Flow*: Tampering, Information Disclosure, Denial of Service.
   * *Data Store*: Tampering, Information Disclosure, Repudiation, Denial of Service.
   * *Process*: Spoofing, Tampering, Information Disclosure, Denial of Service, Elevation of Privilege.
3. **Kuantifikasi Risiko (Prioritize)**: Menggunakan skor *DREAD* (Damage, Reproducibility, Exploitability, Affected Users, Discoverability) skala 1-10 untuk menentukan prioritas.
4. **Mitigasi Arsitektur (Mitigate)**: Memilih strategi: Redesain (Eliminate), Terapkan Kontrol (Mitigate), Alihkan Risiko (Transfer via third-party/insurance), atau Terima Risiko terhitung (Accept).

### 2. Mekanisme Envelope Encryption End-to-End
Proses penulisan dan pembacaan data terenkripsi:
1. **Enkripsi Data (Write Path)**:
   * Aplikasi meminta DEK baru ke KMS dengan menyertakan referensi `KEK_ID` dan metadata konteks enkripsi (*Encryption Context*).
   * KMS menghasilkan DEK plaintext (*Plaintext DEK*) dan mengenkripsi salinan DEK tersebut menggunakan KEK di dalam HSM (*Encrypted DEK* / Ciphertext DEK).
   * KMS mengirimkan kedua nilai tersebut ke aplikasi.
   * Aplikasi mengenkripsi payload data menggunakan *Plaintext DEK* dengan cipher simetris terotentikasi (contoh: AES-GCM-256).
   * Aplikasi **segera menghapus** *Plaintext DEK* dari memori (RAM).
   * Aplikasi menyimpan paket: `[Ciphertext Data] + [Encrypted DEK] + [Initialization Vector (IV)] + [Auth Tag]` ke dalam database penyimpanan.
2. **Dekripsi Data (Read Path)**:
   * Aplikasi membaca paket terenkripsi dari database.
   * Aplikasi mengirimkan `Encrypted DEK` dan `Encryption Context` ke KMS.
   * KMS memverifikasi konteks dan hak akses IAM, kemudian mendekripsi DEK menggunakan KEK di dalam HSM.
   * KMS mengembalikan `Plaintext DEK` ke aplikasi.
   * Aplikasi mendekripsi `Ciphertext Data` menggunakan `Plaintext DEK`, memvalidasi Auth Tag, lalu menghapus `Plaintext DEK` dari RAM.

### 3. Alur Eksekusi Zero-Trust & ABAC Enforcement
Setiap transaksi yang melintasi sistem diproses melalui alur berikut:
1. Klien mengirim permintaan dengan membawa token identitas (contoh: mTLS client certificate + JWT OIDC).
2. **PEP (Policy Enforcement Point)** mencegat koneksi masuk.
3. PEP mengekstraksi atribut kontekstual:
   * Subjek: Identitas pengguna, grup, level otentikasi MFA, usia sesi.
   * Sumber/Perangkat: IP, status enkripsi disk perangkat, integritas TPM/device posture.
   * Objek: Resource ID, klasifikasi kerahasiaan data (e.g., Confidential/Restricted).
   * Aksi: `HTTP POST`, RPC method `ExecuteTransaction`.
   * Lingkungan: Waktu akses, deteksi anomali geolokasi, tingkat ancaman sistem secara keseluruhan.
4. PEP meneruskan konteks ke **PDP (Policy Decision Point)** via gRPC request cepat.
5. PDP mengevaluasi sekumpulan aturan deklaratif (misal via OPA / Rego atau Cedar Engine).
6. PDP mengembalikan status `ALLOW` atau `DENY`, lengkap dengan batasan tambahan (*obligations*, misal: masking atribut tertentu pada respon).
7. PEP menegakkan keputusan tersebut: mengeksekusi koneksi ke backend atau segera melempar error `403 Forbidden` / memutus TCP reset.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Diagram 1: Threat Model Data Flow Diagram (DFD) dengan STRIDE Trust Boundaries

```
[ UNTRUSTED ZONE (Public Internet) ]
      |
      | 1. HTTP/TLS (Spoofing, DoS, Info Leak)
      v
+===================== TRUST BOUNDARY 1 (Edge Ingress) =====================+
|                                                                           |
|   +-----------------------+                                               |
|   | Edge Reverse Proxy    |                                               |
|   | & WAF / API Gateway   |                                               |
|   +-----------+-----------+                                               |
|               |                                                           |
|               | 2. mTLS (Tampering, Elevation of Privilege)              |
|               v                                                           |
+===============|===== TRUST BOUNDARY 2 (Internal Compute Mesh) ============+
|               |                                                           |
|   +-----------v-----------+         3. AuthZ Check        +-----------+   |
|   | Identity Aware PEP    | ----------------------------> | PDP/OPA   |   |
|   | (Envoy Sidecar)       | <---------------------------- | Engine    |   |
|   +-----------+-----------+         Allow / Deny          +-----------+   |
|               |                                                           |
|               | 4. Sanitized Internal RPC                                 |
|               v                                                           |
|   +-----------------------+                                               |
|   | Core Transaction      |                                               |
|   | Microservice (App)    |                                               |
|   +-----+-----------+-----+                                               |
|         |           |                                                     |
+=========|===========|== TRUST BOUNDARY 3 (Data Stores & HSM/KMS) =========+
|         |           |                                                     |
|         | 5. DEK    | 6. Ciphertext + Encrypted DEK                       |
|         |    Req    |                                                     |
|         v           v                                                     |
|   +-----------+   +---------------+                                       |
|   | Hardware  |   | Immutable     |                                       |
|   | KMS / HSM |   | Storage / DB  |                                       |
|   +-----------+   +---------------+                                       |
|                                                                           |
+===========================================================================+
```

### Diagram 2: NIST SP 800-207 Zero-Trust Architecture Engine

```
                   +---------------------------------------+
                   |             CONTROL PLANE             |
                   |                                       |
                   |    +-----------------------------+    |
                   |    |        Policy Engine        |    |
                   |    |            (PE)             |    |
                   |    +--------------+--------------+    |
                   |                   |                   |
                   |                   v                   |
                   |    +-----------------------------+    |
+----------------+ |    |    Policy Administrator     |    | +------------------+
| Context Feeds: | |    |            (PA)             |    | | Context Feeds:   |
| * Threat Intel | |--->+--------------+--------------+<---| | * SIEM / SOAR    |
| * Device Health| |                   |                   | | * PKI / CA       |
| * IAM / IDP    | |                   | Control Config    | | * Data Policies  |
+----------------+ +-------------------|-------------------+ +------------------+
                                       |
=======================================|======================================
                                       v
                   +---------------------------------------+
                   |              DATA PLANE               |
                   |                                       |
+--------------+   |        +---------------------+        |   +--------------+
|   Subject    |   |        |  Policy Enforcement |        |   |   Resource   |
|   (Client/   |===>=======>|     Point (PEP)     |===>===>===>|   Target     |
|   Service)   |   | Intercepted    Proxy         | Granted|   |  (Database/  |
+--------------+   | Connection                   | Conduit|   |  Service)    |
                   |        +---------------------+        |   +--------------+
                   +---------------------------------------+
```

### Diagram 3: Envelope Encryption Pipeline (Write & Read Paths)

```
[ WRITE PATH ]
  
  App Worker                   Cloud KMS / HSM                  Storage Engine
      |                               |                                |
      | 1. GenerateDataKey(KEK_ID)    |                                |
      |------------------------------>|                                |
      |                               | (Generates 256-bit Key)        |
      |                               | (Encrypts Key using KEK)       |
      | 2. Plaintext DEK + Enc DEK    |                                |
      |<------------------------------|                                |
      |                                                                |
      |--+ Encrypt Data with Plaintext DEK                             |
      |  | using AES-256-GCM                                           |
      |<-+ Zero-out Plaintext DEK memory                               |
      |                                                                |
      | 3. Store: [IV + Ciphertext + Tag + Encrypted DEK]              |
      |--------------------------------------------------------------->|

-----------------------------------------------------------------------------

[ READ PATH ]

  App Worker                   Cloud KMS / HSM                  Storage Engine
      |                               |                                |
      | 1. Read Payload               |                                |
      |<---------------------------------------------------------------|
      |                               |                                |
      | 2. Decrypt(Encrypted DEK)     |                                |
      |------------------------------>|                                |
      |                               | (HSM Decrypts DEK via KEK)     |
      | 3. Return Plaintext DEK       |                                |
      |<------------------------------|                                |
      |                                                                |
      |--+ Decrypt Ciphertext with Plaintext DEK                       |
      |  | Verify Auth Tag                                             |
      |<-+ Zero-out Plaintext DEK memory                               |
      |                                                                |
      | [Plaintext Result in Memory]                                   |
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi Go murni untuk **Attribute-Based Access Control (ABAC)** Engine sederhana. Contoh ini mendemonstrasikan evaluasi aturan dinamis tanpa dependensi eksternal, memvalidasi hak akses subjek terhadap objek berdasarkan atribut kontekstual.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"time"
)

type Classification string

const (
	Public       Classification = "PUBLIC"
	Confidential Classification = "CONFIDENTIAL"
	Restricted   Classification = "RESTRICTED"
)

// Subject merepresentasikan entitas yang melakukan request
type Subject struct {
	ID                 string
	Roles              []string
	ClearanceLevel     Classification
	IsMFAAuthenticated bool
	DeviceCompliant    bool
}

// Resource merepresentasikan objek yang diakses
type Resource struct {
	ID             string
	Classification Classification
	OwnerID        string
}

// Action mendefinisikan operasi
type Action string

const (
	ActionRead  Action = "READ"
	ActionWrite Action = "WRITE"
)

// Environment mendefinisikan konteks operasional
type Environment struct {
	RequestTime     time.Time
	IsInternalIP    bool
	ThreatLevelHigh bool
}

// SecurityContext membungkus keseluruhan kondisi evaluasi
type SecurityContext struct {
	Subject     Subject
	Resource    Resource
	Action      Action
	Environment Environment
}

// PolicyRule adalah fungsi yang mengembalikan keputusan evaluasi
type PolicyRule func(ctx SecurityContext) (bool, error)

type ABACEngine struct {
	rules []PolicyRule
}

func NewABACEngine() *ABACEngine {
	return &ABACEngine{rules: make([]PolicyRule, 0)}
}

func (e *ABACEngine) RegisterRule(rule PolicyRule) {
	e.rules = append(e.rules, rule)
}

// Evaluate memeriksa semua aturan. Mengikuti prinsip "Default Deny".
func (e *ABACEngine) Evaluate(ctx context.Context, secCtx SecurityContext) (bool, error) {
	if len(e.rules) == 0 {
		return false, errors.New("no policy rules configured; fail-closed by default")
	}

	for _, rule := range e.rules {
		allowed, err := rule(secCtx)
		if err != nil {
			return false, fmt.Errorf("policy evaluation error: %w", err)
		}
		if !allowed {
			return false, nil // Eksplisit Deny jika salah satu aturan gagal
		}
	}

	return true, nil
}

func main() {
	engine := NewABACEngine()

	// Rule 1: Akses ke data Restricted membutuhkan MFA dan device yang tersertifikasi
	engine.RegisterRule(func(ctx SecurityContext) (bool, error) {
		if ctx.Resource.Classification == Restricted {
			if !ctx.Subject.IsMFAAuthenticated || !ctx.Subject.DeviceCompliant {
				return false, nil
			}
		}
		return true, nil
	})

	// Rule 2: Clearance Level subjek harus setara atau lebih tinggi dari Resource
	engine.RegisterRule(func(ctx SecurityContext) (bool, error) {
		clearanceOrder := map[Classification]int{
			Public:       1,
			Confidential: 2,
			Restricted:   3,
		}

		if clearanceOrder[ctx.Subject.ClearanceLevel] < clearanceOrder[ctx.Resource.Classification] {
			return false, nil
		}
		return true, nil
	})

	// Rule 3: Jika threat level sistem tinggi, tolak penulisan dari non-internal network
	engine.RegisterRule(func(ctx SecurityContext) (bool, error) {
		if ctx.Environment.ThreatLevelHigh && ctx.Action == ActionWrite && !ctx.Environment.IsInternalIP {
			return false, nil
		}
		return true, nil
	})

	// Skenario: Engineer mencoba mengakses data Restricted dari laptop compliant dengan MFA
	ctxValid := SecurityContext{
		Subject: Subject{
			ID:                 "emp-1092",
			ClearanceLevel:     Restricted,
			IsMFAAuthenticated: true,
			DeviceCompliant:    true,
		},
		Resource: Resource{
			ID:             "financial-ledger-2026",
			Classification: Restricted,
			OwnerID:        "finance-dept",
		},
		Action: ActionRead,
		Environment: Environment{
			RequestTime:     time.Now(),
			IsInternalIP:    true,
			ThreatLevelHigh: false,
		},
	}

	allowed, err := engine.Evaluate(context.Background(), ctxValid)
	if err != nil {
		panic(err)
	}
	fmt.Printf("[Skenario 1] Akses Diberikan: %v\n", allowed) // Harapan: true

	// Skenario 2: Engineer yang sama mencoba mengakses data tanpa MFA
	ctxInvalid := ctxValid
	ctxInvalid.Subject.IsMFAAuthenticated = false

	allowedInvalid, _ := engine.Evaluate(context.Background(), ctxInvalid)
	fmt.Printf("[Skenario 2] Akses Diberikan (Tanpa MFA): %v\n", allowedInvalid) // Harapan: false
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah implementasi kelas enterprise untuk arsitektur **Envelope Encryption** menggunakan algoritma **AES-256-GCM** yang dilengkapi dengan simulasi *KMS Mock* thread-safe, rotasi kunci, dan *Associated Authenticated Data (AAD)* untuk mencegah *ciphertext reuse attack*.

```go
package main

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"errors"
	"fmt"
	"io"
	"sync"
)

// KMSClient mendefinisikan kontrak interaksi dengan KMS/HSM (AWS KMS, GCP KMS, Vault)
type KMSClient interface {
	GenerateDataKey(kekID string) (plaintextDEK []byte, ciphertextDEK []byte, err error)
	DecryptDataKey(kekID string, ciphertextDEK []byte) (plaintextDEK []byte, err error)
}

// MockHSMKMS mensimulasikan KMS yang menyimpan Master Key (KEK) di dalam memori terisolasi
type MockHSMKMS struct {
	mu   sync.RWMutex
	keks map[string][]byte
}

func NewMockHSMKMS() *MockHSMKMS {
	return &MockHSMKMS{
		keks: make(map[string][]byte),
	}
}

func (m *MockHSMKMS) RegisterKEK(kekID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	key := make([]byte, 32) // AES-256
	if _, err := io.ReadFull(rand.Reader, key); err != nil {
		return err
	}
	m.keks[kekID] = key
	return nil
}

func (m *MockHSMKMS) GenerateDataKey(kekID string) ([]byte, []byte, error) {
	m.mu.RLock()
	kek, exists := m.keks[kekID]
	m.mu.RUnlock()
	if !exists {
		return nil, nil, errors.New("KEK tidak ditemukan")
	}

	// 1. Generate Plaintext DEK (256-bit)
	plaintextDEK := make([]byte, 32)
	if _, err := io.ReadFull(rand.Reader, plaintextDEK); err != nil {
		return nil, nil, err
	}

	// 2. Encrypt DEK menggunakan KEK (AES-GCM)
	block, err := aes.NewCipher(kek)
	if err != nil {
		return nil, nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, nil, err
	}

	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, nil, err
	}

	ciphertextDEK := gcm.Seal(nonce, nonce, plaintextDEK, nil)

	return plaintextDEK, ciphertextDEK, nil
}

func (m *MockHSMKMS) DecryptDataKey(kekID string, ciphertextDEK []byte) ([]byte, error) {
	m.mu.RLock()
	kek, exists := m.keks[kekID]
	m.mu.RUnlock()
	if !exists {
		return nil, errors.New("KEK tidak ditemukan")
	}

	block, err := aes.NewCipher(kek)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}

	nonceSize := gcm.NonceSize()
	if len(ciphertextDEK) < nonceSize {
		return nil, errors.New("malformed ciphertext DEK")
	}

	nonce, actualCiphertext := ciphertextDEK[:nonceSize], ciphertextDEK[nonceSize:]
	plaintextDEK, err := gcm.Open(nil, nonce, actualCiphertext, nil)
	if err != nil {
		return nil, fmt.Errorf("dekripsi DEK gagal: integritas rusak: %w", err)
	}

	return plaintextDEK, nil
}

// EncryptedPayload adalah amplop data yang aman disimpan di database publik/untrusted
type EncryptedPayload struct {
	KEKID         string `json:"kek_id"`
	EncryptedDEK  []byte `json:"encrypted_dek"`
	Nonce         []byte `json:"nonce"`
	Ciphertext    []byte `json:"ciphertext"`
	ContextDigest []byte `json:"context_digest"` // Hash dari Encryption Context (AAD)
}

// EnvelopeEncryptor mengelola siklus enkripsi/dekripsi tingkat aplikasi
type EnvelopeEncryptor struct {
	kms KMSClient
}

func NewEnvelopeEncryptor(kms KMSClient) *EnvelopeEncryptor {
	return &EnvelopeEncryptor{kms: kms}
}

// zeroize menghapus jejak memori secara defensif
func zeroize(data []byte) {
	for i := range data {
		data[i] = 0
	}
}

func (ee *EnvelopeEncryptor) Encrypt(plaintext []byte, kekID string, contextAAD []byte) (*EncryptedPayload, error) {
	// Dapatkan DEK baru dari KMS
	plainDEK, encDEK, err := ee.kms.GenerateDataKey(kekID)
	if err != nil {
		return nil, fmt.Errorf("gagal mendapatkan data key: %w", err)
	}
	defer zeroize(plainDEK) // JAMINAN: Kunci plaintext segera dimusnahkan dari RAM

	// Inisialisasi Cipher AES-GCM dengan Plaintext DEK
	block, err := aes.NewCipher(plainDEK)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}

	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, err
	}

	// Enkripsi data plaintext dengan AAD (Additional Authenticated Data) untuk mencegah replay/tamper context
	ciphertext := gcm.Seal(nil, nonce, plaintext, contextAAD)

	aadHash := sha256.Sum256(contextAAD)

	return &EncryptedPayload{
		KEKID:         kekID,
		EncryptedDEK:  encDEK,
		Nonce:         nonce,
		Ciphertext:    ciphertext,
		ContextDigest: aadHash[:],
	}, nil
}

func (ee *EnvelopeEncryptor) Decrypt(payload *EncryptedPayload, contextAAD []byte) ([]byte, error) {
	// Verifikasi keaslian konteks sebelum memanggil KMS (Optimasi fail-fast)
	expectedHash := sha256.Sum256(contextAAD)
	if string(payload.ContextDigest) != string(expectedHash[:]) {
		return nil, errors.New("konteks enkripsi tidak valid: AAD mismatch")
	}

	// Minta KMS mendekripsi DEK
	plainDEK, err := ee.kms.DecryptDataKey(payload.KEKID, payload.EncryptedDEK)
	if err != nil {
		return nil, fmt.Errorf("KMS menolak pembukaan DEK: %w", err)
	}
	defer zeroize(plainDEK) // JAMINAN: Kunci plaintext segera dimusnahkan dari RAM

	block, err := aes.NewCipher(plainDEK)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}

	plaintext, err := gcm.Open(nil, payload.Nonce, payload.Ciphertext, contextAAD)
	if err != nil {
		return nil, fmt.Errorf("dekripsi payload gagal: data rusak atau telah dimanipulasi: %w", err)
	}

	return plaintext, nil
}

func main() {
	// Inisialisasi KMS Mock
	kms := NewMockHSMKMS()
	masterKeyID := "arn:aws:kms:ap-southeast-3:112233445566:key/prod-customer-data"
	if err := kms.RegisterKEK(masterKeyID); err != nil {
		panic(err)
	}

	encryptor := NewEnvelopeEncryptor(kms)

	// Data rahasia tingkat tinggi (PII/Finansial)
	sensitifPayload := []byte("NIK: 3171000000000001; Gaji Pokok: IDR 120.000.000; Saldo: IDR 1.500.000.000")
	aadContext := []byte("tenant_id=corp_alpha;table=salaries;row_id=row_8912")

	fmt.Println("=== ENKRIPSI DATA MENGGUNAKAN ENVELOPE ENCRYPTION ===")
	envelope, err := encryptor.Encrypt(sensitifPayload, masterKeyID, aadContext)
	if err != nil {
		panic(err)
	}

	fmt.Printf("Ciphertext DEK Length: %d bytes\n", len(envelope.EncryptedDEK))
	fmt.Printf("Ciphertext Payload: %x... (truncated)\n", envelope.Ciphertext[:24])
	fmt.Printf("Nonce: %x\n", envelope.Nonce)

	fmt.Println("\n=== DEKRIPSI DATA BERHASIL (VALID CONTEXT) ===")
	decrypted, err := encryptor.Decrypt(envelope, aadContext)
	if err != nil {
		panic(err)
	}
	fmt.Printf("Hasil Dekripsi: %s\n", string(decrypted))

	fmt.Println("\n=== ATTEMPT: DEKRIPSI DENGAN MEMALSUKAN KONTEKS AAD ===")
	fakeContext := []byte("tenant_id=corp_beta;table=salaries;row_id=row_8912")
	_, err = encryptor.Decrypt(envelope, fakeContext)
	if err != nil {
		fmt.Printf("Mitigasi Berhasil! Serangan Terdeteksi: %v\n", err)
	}
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Dalam merancang arsitektur keamanan dan Zero Trust, tidak ada solusi perak (*silver bullet*). Setiap kontrol menambahkan biaya langsung pada sistem.

### 1. Matrix Trade-Off Otorisasi: RBAC vs ABAC vs ReBAC

| Dimensi | RBAC | ABAC | ReBAC (Zanzibar) |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Implementasi** | Sangat Rendah | Sedang hingga Tinggi | Ekstrem (Membutuhkan Graph DB / Dedicated Cluster) |
| **Ekspresivitas Kebijakan** | Kaku (Hanya Peran Statis) | Sangat Tinggi (Waktu, Lokasi, Perangkat) | Tinggi (Hubungan Hirarkis & Kepemilikan) |
| **Latensi Evaluasi** | $O(1)$ Lookup Cepat | $O(N)$ Bergantung jumlah aturan & fetch context | $O(\log V)$ Graph traversal dengan caching masif |
| **Role/Rule Explosion** | Resiko Tinggi *Role Explosion* | Resiko *Policy Sprawl* (sulit diaudit) | Kompleksitas definisi schema relasi |
| **Kesesuaian Use-Case** | Internal Admin Portal, SaaS Sederhana | Perbankan, Regulasi Ketat, IoT, B2B Multi-Tenant | Google Docs, GitHub, B2C Skala Miliar Entitas |

### 2. Centralized PDP vs Distributed PEP (Sidecar)

* **Centralized Policy Decision Point (PDP)**:
  * *Kelebihan*: Konsistensi mutlak; pembaruan aturan keamanan langsung berefek seketika (*zero propagation lag*).
  * *Kekurangan*: Menjadi *Single Point of Failure (SPOF)*; menambahkan *network hop* tambahan (latensi +5-20ms per RPC); membatasi throughput sistem terdistribusi.
* **Distributed PEP with Embedded/Local PDP (e.g., Envoy + OPA Sidecar / Local Cache)**:
  * *Kelebihan*: Performa tinggi, evaluasi lokal sub-milidetik, tahan terhadap *network partition* parsial.
  * *Kekurangan*: Membutuhkan konsistensi akhirnya (*eventual consistency*) dalam sinkronisasi aturan; konsumsi memori meningkat di setiap container/node.

### 3. Cryptographic Performance vs Granularity

* **Database Column-Level vs Field-Level vs Storage (TDE) Encryption**:
  * *Transparent Data Encryption (TDE)*: Mengamankan fisik disk dari pencurian fisik, namun nol proteksi terhadap serangan *SQL Injection* atau kebocoran kredensial aplikasi. *Overhead CPU: < 2%*.
  * *Application-Level Envelope Encryption (Field-Level)*: Proteksi tertinggi (bahkan DBA tidak bisa melihat plaintext). *Overhead*: Peningkatan ukuran penyimpanan (*ciphertext expansion* + metadata) sebesar ~40-100%, peningkatan latensi eksekusi serialisasi/dekripsi, serta hilangnya kemampuan *native SQL search* tanpa skema kompleks (*Order-Preserving / Homomorphic Encryption* yang lambat dan rapuh).

---

## SEKSI 11 — BEST PRACTICES

1. **Prinsip Fail-Closed (Default Deny)**:
   Arsitektur keamanan harus secara baku menolak akses (*deny by default*). Kegagalan pada komponen pengecekan (misal: timeout koneksi ke PDP atau error parsing konfigurasi) harus menghasilkan status pembatalan/penolakan akses, bukan lolos (*fail-open*).
2. **Kriptografi yang Diautentikasi (Authenticated Encryption with Associated Data - AEAD)**:
   Selalu gunakan cipher mode AEAD seperti `AES-GCM` atau `ChaCha20-Poly1305`. Jangan pernah menggunakan cipher stream/block murni (seperti AES-CBC atau AES-ECB) tanpa HMAC terpisah (*Encrypt-then-MAC*), untuk mencegah serangan *padding oracle* dan *bit-flipping*.
3. **Pemberian Identitas Kriptografis untuk Setiap Workload**:
   Gunakan standar **SPIFFE/SPIRE** untuk menyematkan identitas kriptografis (*X.509 SVID*) berumur pendek (*ephemeral*) ke setiap proses atau pod. Hindari membagikan *long-lived static API keys* antar microservices.
4. **Isolasi Zero-Knowledge pada Penyimpanan**:
   Arsitek sistem tidak boleh memegang kunci utama bersama dengan data. Pisahkan entitas infrastruktur cloud: simpan data di *Region A / Provider X*, sementara KMS/HSM dikontrol di bawah regulasi entitas independen atau *Cloud Hardware Security Module* tersertifikasi *FIPS 140-2 Level 3*.
5. **Rotasi Kunci Otomatis (Crypto-Agility)**:
   Desain format ciphertext dengan menyertakan *Key Version Header*. Hal ini memungkinkan rotasi KEK secara terjadwal (misal: setiap 90 hari) tanpa perlu langsung melakukan *re-encrypt* seluruh database historis secara masal (*decrypt on read, re-encrypt on write*).
6. **Immutable & Append-Only Audit Logging**:
   Seluruh mutasi hak akses dan evaluasi penolakan PDP wajib dicatat ke dalam media penyimpanan append-only (misal: AWS S3 dengan *Object Lock*, atau Kafka dengan retensi terdistribusi dan cryptographic chaining), yang dikirimkan secara *out-of-band* sehingga penyerang dengan hak root tidak dapat menghapus jejaknya.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The "JWT as a Silver Bullet" Fallacy
* *Anti-Pattern*: Menggunakan JWT tanpa state (*stateless JWT*) untuk otorisasi berumur panjang (misal: expired dalam 24 jam) tanpa kemampuan pencabutan (*revocation mechanism*). Ketika kredensial atau peran pengguna dicabut, pengguna tetap memiliki akses legal hingga token kedaluwarsa.
* *Solusi*: Buat access token berumur sangat pendek (5-15 menit). Gunakan refresh token rotation terpusat, atau implementasikan *Back-Channel Logout* dan *Token Revocation List* terdistribusi berbasis Bloom Filter atau Redis pub-sub.

### 2. Confused Deputy Vulnerability
* *Anti-Pattern*: Service A meminta Service B untuk melakukan operasi atas nama Pengguna X, namun Service B hanya memverifikasi identitas Service A tanpa memeriksa apakah Pengguna X memiliki wewenang sah atas objek yang diminta.
* *Solusi*: Terapkan *Identity Chaining* atau pertukaran token berbasis OAuth 2.0 Token Exchange (RFC 8693) di mana delegasi identitas pengguna awal (*Actor Token*) diteruskan melintasi seluruh rantai RPC internal.

### 3. Replay Attacks via Nonce / IV Reuse pada GCM
* *Anti-Pattern*: Menggunakan kembali *Initialization Vector (IV)* atau Nonce yang sama dengan kunci AES-GCM yang sama.
* *Dampak Fatal*: Menghasilkan kerentanan fatal hilangnya kerahasiaan (*catastrophic plaintext recovery*) dan pemalsuan tag otentikasi (*authentication forgery*).
* *Solusi*: Pastikan nonces bersifat kriptografis unik via `crypto/rand` atau gunakan skema counter terisolasi yang dijamin tidak akan pernah bentrok sepanjang masa pakai kunci. Batasi enkripsi maksimal $2^{32}$ pesan untuk satu pasang DEK.

### 4. BOLA (Broken Object Level Authorization) / IDOR
* *Anti-Pattern*: API hanya memverifikasi apakah pemanggil memiliki token login yang valid (`isAuthenticated`), tetapi melewatkan verifikasi apakah objek target (e.g., `/api/orders/{id}`) benar-benar dimiliki oleh pemanggil tersebut.
* *Solusi*: Integrasikan pemeriksaan kepemilikan relasional pada data repository layer secara native atau lewat interceptor PEP yang mengecek relasi kepemilikan.

### 5. Membiarkan Algoritma Kriptografi 'None' atau Fallback ke Plaintext
* *Anti-Pattern*: Memverifikasi tanda tangan JWT dengan mempercayai *header parameter* `alg` secara langsung dari klien tanpa validasi whitelist di server, membuka celah eksploitasi `alg: "none"`.
* *Solusi*: Hardcode algoritma ekspektasi verifikasi di sisi verifikator (contoh: secara tegas hanya menerima `ES384` atau `RS256`).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Threat Model Matrix Construction (Tingkat Pemula)
* **Skenario**: Anda merancang sistem transfer dana antar-bank (*Inter-Bank Payment Gateway*). Sistem menerima request dari Web Client -> Masuk Ingress NGINX -> Diteruskan ke Transaction Orchestrator Service -> Mengakses Database Transaksi dan Core Banking System (Third-Party).
* **Tugas**:
  1. Identifikasi minimal 3 *Trust Boundaries*.
  2. Susun matriks STRIDE lengkap (minimal 1 ancaman nyata untuk setiap huruf STRIDE).
  3. Berikan usulan kontrol arsitektur mitigasi konkret untuk masing-masing ancaman tersebut.

### Latihan 2: Implementasi Dynamic Token Revocation Interceptor (Tingkat Menengah)
* **Tugas**:
  1. Buat sebuah HTTP middleware di Go yang memvalidasi bearer token JWT.
  2. Implementasikan mekanisme revocasi menggunakan Bloom Filter atau Redis/In-Memory Cache untuk mendeteksi `jti` (JWT ID) yang telah dibatalkan sebelum token masa berlakunya usai.
  3. Buktikan middleware mengembalikan status `401 Unauthorized` seketika saat `jti` ditandai revocated, meski signature kriptografis JWT masih valid secara matematis.

### Latihan 3: Arsitektur Zero-Trust mTLS dengan SPIFFE/SPIRE (Tingkat Lanjut)
* **Skenario**: Terdapat Microservice A (Frontend) dan Microservice B (Payment Gateway). Microservice B hanya boleh menerima koneksi TLS dari Microservice A, bukan dari sembarang pod dalam cluster Kubernetes.
* **Tugas**:
  1. Tuliskan manifest konfigurasi Envoy Sidecar atau program Golang `crypto/tls` native yang mengonfigurasi `ClientAuth: tls.RequireAndVerifyClientCert`.
  2. Implementasikan *Custom Verification Logic* yang mengekstrak SAN (*Subject Alternative Name*) dari sertifikat klien (bertipe URI) dan mencocokkannya secara ketat dengan identitas SPIFFE ID: `spiffe://cluster.local/ns/production/sa/frontend-service-account`.
  3. Tolak koneksi seketika pada level TLS Handshake jika SPIFFE ID tidak cocok, tanpa mengeksekusi HTTP router layer.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk menguji pemahaman arsitektur Anda:

1. **Manakah dari pernyataan berikut yang secara akurat membedakan peranan KEK (Key Encryption Key) dan DEK (Data Encryption Key) dalam arsitektur Envelope Encryption?**
   * A. KEK digunakan untuk mengenkripsi payload data berukuran besar, sedangkan DEK digunakan untuk mengautentikasi pengguna ke KMS.
   * B. DEK dihasilkan secara unik untuk setiap payload/record data dan mengenkripsi plaintext; KEK berada secara aman di dalam HSM/KMS dan mengenkripsi DEK.
   * C. KEK harus selalu diekspor ke memori aplikasi, sedangkan DEK tidak pernah boleh meninggalkan perimeter fisik HSM.
   * D. DEK menggunakan kriptografi asimetris (RSA-4096), sedangkan KEK secara eksklusif menggunakan algoritma simetris (AES-128).

2. **Dalam implementasi Zero Trust berbasis NIST SP 800-207, di manakah posisi Envoy Proxy yang dipasang sebagai sidecar microservice?**
   * A. Policy Decision Point (PDP)
   * B. Policy Engine (PE)
   * C. Policy Enforcement Point (PEP)
   * D. Policy Administrator (PA)

3. **Mengapa mode enkripsi AES-ECB dan AES-CBC (tanpa MAC) ditolak keras dalam arsitektur keamanan modern untuk data transit maupun rest?**
   * A. Keduanya tidak mendukung ukuran kunci 256-bit.
   * B. Keduanya memiliki kompleksitas algoritma yang menyebabkan overhead CPU melebihi 80%.
   * C. ECB mempertahankan pola data plaintext pada ciphertext, sedangkan CBC rentan terhadap serangan padding oracle dan manipulasi integritas data (bit-flipping).
   * D. Keduanya tidak kompatibel dengan arsitektur komputasi 64-bit modern.

4. **Skenario: Seorang penyerang berhasil mencuri session token atau client credentials dan menggunakannya dari IP address serta device fingerprint yang sama sekali berbeda dengan pola normal. Kontrol arsitektur manakah yang paling efektif menggagalkan serangan ini secara dinamis pada arsitektur ZTA?**
   * A. Penambahan panjang karakter password database.
   * B. Static Role-Based Access Control (RBAC).
   * C. Continuous Adaptive Risk and Trust Assessment (CARTA) yang diintegrasikan ke dalam evaluasi ABAC di PDP.
   * D. Penggunaan hashing bcrypt pada password pengguna.

5. **Apa kelemahan utama model otorisasi RBAC (Role-Based Access Control) murni ketika diterapkan pada sistem perbankan skala besar dengan ratusan cabang dan jutaan nasabah?**
   * A. Tidak mampu melakukan hashing kata sandi.
   * B. Terjadinya fenomena *Role Explosion*, di mana administrator terpaksa membuat ribuan peran statis kombinatorik (contoh: `Teller_BranchJakarta_Level1`, `Teller_BranchBandung_Level2`).
   * C. RBAC tidak dapat diintegrasikan dengan database SQL.
   * D. RBAC menuntut infrastruktur HSM perangkat keras khusus.

---

### Kunci Jawaban & Evaluasi

* **1: B** — KEK memproteksi DEK di dalam batas aman HSM; DEK memproteksi plaintext data secara terdistribusi sehingga KMS tidak mengalami bottleneck enkripsi data besar.
* **2: C** — Envoy bertindak sebagai PEP di *Data Plane*, yang mencegat trafik jaringan dan menegakkan keputusan dari PDP (*Control Plane*).
* **3: C** — Kriptografi modern mewajibkan AEAD (*Authenticated Encryption*). ECB membocorkan struktur pola visual/data, dan CBC tanpa HMAC rentan terhadap eksploitasi integritas dan padding.
* **4: C** — ZTA mengevaluasi konteks lingkungan (perubahan anomali IP, device posture, geolokasi) secara kontinu via ABAC/PDP, bukan sekadar memvalidasi masa berlaku statis token.
* **5: B** — RBAC tidak memiliki dimensi atribut kontekstual. Menambahkan variasi lokasi, waktu, dan batas limit transaksi ke dalam peran statis selalu berujung pada ledakan jumlah peran (*role explosion*).

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Standar Keamanan Internasional & Buku Putih**:
   * *NIST Special Publication 800-207*: "Zero Trust Architecture" (National Institute of Standards and Technology).
   * *Google Cloud BeyondCorp*: Rangkaian whitepaper perintis implementasi Zero Trust global.
   * *Zanzibar: Google’s Consistent, Global Authorization System* (Makalah USENIX ATC 2019).
2. **Buku Rekomendasi Arsitek**:
   * *Designing Secure Software* oleh Loren Kohnfelder (Pencipta STRIDE), No Starch Press.
   * *Zero Trust Networks: Building Secure Systems in Untrusted Networks* oleh Evan Gilman & Doug Barth, O'Reilly Media.
   * *Real-World Cryptography* oleh David Wong, Manning Publications.
3. **Spesifikasi Protokol Kriptografi & Identitas**:
   * *RFC 8446*: The Transport Layer Security (TLS) Protocol Version 1.3.
   * *RFC 7519*: JSON Web Token (JWT).
   * *SPIFFE Standard*: Secure Production Identity Framework for Everyone (spiffe.io).
   * *Open Policy Agent (OPA)*: openpolicyagent.org Documentation & Cedar Policy Language (cedarpolicy.com).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Pergeseran Paradigma**: Keamanan perimeter tradisional (*Castle-and-Moat*) telah usang. Arsitektur modern wajib mengadopsi postulat **Zero Trust (ZTA)**: *Never Trust, Always Verify*, dan *Assume Breach*.
2. **Threat Modeling Bukan Opsional**: STRIDE merupakan proses dekomposisi sistemik untuk mendeteksi kerentanan arsitektural (*Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation of Privilege*) pada fase desain, menghemat biaya perbaikan ratusan kali lipat.
3. **Pertahanan Berlapis (Defense in Depth)**: Keamanan tidak boleh bergantung pada satu kontrol tunggal. Perlindungan harus diterapkan secara independen melintasi lapisan Jaringan, Host, Runtime, Aplikasi, Data, dan Identitas.
4. **Envelope Encryption & Cryptographic Integrity**: Selalu gunakan cipher berbasis AEAD (e.g., `AES-256-GCM`). Amankan data menggunakan *Envelope Encryption* (DEK terpisah per objek, KEK diisolasi di HSM/KMS) yang dilengkapi *Associated Authenticated Data (AAD)* untuk mencegah *replay/confused context attacks*.
5. **Evolusi Otorisasi**: Transisi dari model kaku **RBAC** menuju **ABAC** (konteks atribut lingkungan dinamis) dan **ReBAC** (grafik relasi berbasis model Google Zanzibar) merupakan keharusan untuk menangani kompleksitas sistem skala besar dan mencegah kerentanan BOLA/IDOR.

---

## SEKSI 17 — GLOSARIUM

* **ABAC (Attribute-Based Access Control)**: Paradigma otorisasi yang mengevaluasi hak akses menggunakan kombinasi atribut subjek, resource, aksi, dan konteks lingkungan.
* **AEAD (Authenticated Encryption with Associated Data)**: Skema enkripsi yang secara bersamaan menjamin kerahasiaan (*confidentiality*) dan integritas (*authenticity*) data beserta metadata yang tidak terenkripsi.
* **BOLA (Broken Object Level Authorization)**: Kerentanan di mana pengguna dapat mengakses objek yang bukan miliknya hanya dengan mengubah identifier pada request API.
* **CARTA (Continuous Adaptive Risk and Trust Assessment)**: Pendekatan strategis evaluasi risiko keamanan dan keputusan akses secara real-time dan berkelanjutan.
* **DEK (Data Encryption Key)**: Kunci kriptografi simetris yang digunakan langsung untuk mengenkripsi payload data mentah.
* **HSM (Hardware Security Module)**: Perangkat keras komputasi fisik tersertifikasi tahan-rusak (*tamper-resistant*) yang didedikasikan untuk operasi kriptografi dan penyimpanan kunci privat.
* **KEK (Key Encryption Key)**: Kunci induk kriptografi tingkat tinggi yang digunakan secara eksklusif untuk mengenkripsi dan memproteksi DEK.
* **mTLS (Mutual TLS)**: Proses autentikasi dua arah di mana kedua belah pihak (klien dan server) saling memverifikasi sertifikat X.509 masing-masing melalui protokol TLS.
* **PDP (Policy Decision Point)**: Komponen logis arsitektur keamanan yang bertugas mengevaluasi kebijakan dan mengeluarkan keputusan otorisasi (Allow/Deny).
* **PEP (Policy Enforcement Point)**: Komponen yang mencegat aliran komunikasi dan menegakkan keputusan yang dikeluarkan oleh PDP.
* **ReBAC (Relationship-Based Access Control)**: Model otorisasi yang mengekspresikan aturan akses berdasarkan jaringan hubungan/relasi antar entitas (subjek dan objek).
* **SPIFFE (Secure Production Identity Framework for Everyone)**: Standar terbuka yang mendefinisikan identitas terverifikasi bagi beban kerja perangkat lunak di lingkungan dinamis/cloud-native.
* **STRIDE**: Akronim pemodelan ancaman yang mencakup *Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, dan Elevation of Privilege*.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Pedagogy & Delivery Tip**:
  Saat mengajarkan modul ini, hindari memulai dari rumus matematika kriptografi. Mulailah dari studi kasus nyata insiden pembobolan (*post-mortem analysis*, misal: serangan pembajakan sesi AWS Capital One atau insiden SolarWinds). Tunjukkan bagaimana batas VPC privat gagal membendung pergerakan lateral, lalu perkenalkan ZTA sebagai solusi logis atas kegagalan tersebut.
* **Common Student Misconceptions**:
  Banyak software engineer beranggapan bahwa enkripsi database bawaan (*Transparent Data Encryption / TDE*) sudah cukup untuk keamanan tingkat enterprise. Instruktur harus mendemonstrasikan secara visual bahwa TDE tidak melindungi data sama sekali dari serangan *SQL Injection* atau pencurian kredensial aplikasi, sehingga implementasi *Application-Layer Envelope Encryption* mutlak dipahami.
* **Lab Guidance**:
  Pada Seksi 09, tekankan pentingnya fungsi `zeroize()` untuk membersihkan memori DEK di RAM. Tunjukkan bahwa pada bahasa dengan Garbage Collection seperti Go atau Java, string/slice yang tidak di-zeroize dapat tertinggal di heap memory dump dan diekstraksi penyerang via eksploitasi *Heartbleed-style* atau profiling endpoints.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Maret 2026)**:
  * Rilis inisial kurikulum arsitektur keamanan tingkat lanjut.
  * Standarisasi format modul 20 seksi GEMINI.md.
  * Penambahan kode Envelope Encryption AES-256-GCM thread-safe dan ABAC Engine native Go.
  * Integrasi diagram ASCII untuk NIST SP 800-207 dan Threat Modeling DFD.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `SA-CSD-0701` — Resiliency, Fault Tolerance, and Chaos Engineering
* **Modul Berikutnya**: `SA-CSD-0901` — Observability, Distributed Tracing, Telemetry, and SRE Principles
* **Index Kurikulum Utama**: `SA-ROOT-INDEX` — Senior Technical Curriculum: Software Architect Track