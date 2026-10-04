# MODUL 05: KEAMANAN ENTERPRISE, ZERO-TRUST & KEPATUHAN REGULASI

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: FDE-ARCH-0501
* **Nama Modul**: Keamanan Enterprise, Zero-Trust & Kepatuhan Regulasi: Integrasi Active Directory / LDAP / SAML, Role-Based Access Control, FedRAMP / HIPAA Compliance, Immutable Audit Trails
* **Kategori**: 06-Architecture-and-System-Design
* **Tingkat Kesulitan**: Advanced / Senior Enterprise Level
* **Prasyarat**: 
  * Pemahaman mendalam tentang protokol jaringan TCP/IP, TLS 1.3, dan arsitektur Public Key Infrastructure (PKI).
  * Pengalaman membangun microservices terdistribusi dengan Go, Rust, atau Java.
  * Pemahaman dasar tentang OAuth2, OpenID Connect (OIDC), dan struktur direktori X.500.
* **Target Audiens**: Forward Deployed Engineers (FDE), Enterprise Solutions Architects, Site Reliability Engineers (SRE), dan Security Engineers yang bertugas mengintegrasikan perangkat lunak ke dalam lingkungan on-premise, cloud hibrida, atau lingkungan pemerintah dan perbankan yang memiliki regulasi ketat (*air-gapped* atau *high-compliance*).
* **Alokasi Waktu**: 
  * Teori Komprehensif: 4 Jam
  * Praktik & Implementasi Lapangan: 6 Jam
  * Total: 10 Jam

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur Zero-Trust (NIST SP 800-207)**: Menghilangkan konsep batas jaringan tepercaya (*perimeter-based security*) dan menegakkan validasi identitas, postur perangkat, serta konteks secara berkelanjutan (*continuous verification*).
2. **Mengintegrasikan Sistem Identitas Warisan dan Modern**: Menghubungkan platform deployment dengan sistem identitas enterprise eksisting melalui Active Directory, LDAP, SAML 2.0 WebSSO, dan federasi OIDC menggunakan arsitektur *brokerage*.
3. **Mengonstruksi Model Otorisasi Granular (RBAC/ABAC/PBAC)**: Merancang mesin otorisasi terdesentralisasi menggunakan Open Policy Agent (OPA) berbasis Rego untuk memvalidasi hak akses secara dinamis pada lapisan API gateway dan service mesh.
4. **Memenuhi Kontrol Keamanan FedRAMP High dan HIPAA Security Rule**: Mengimplementasikan segmentasi data ePHI/PII, enkripsi *in-transit* (mTLS) dan *at-rest* (AES-256-GCM / Envelope Encryption dengan KMS), serta batas otorisasi data (*data residency boundary*).
5. **Membangun Sistem Immutable Audit Trail**: Merancang sistem pencatatan audit yang anti-pemalsuan (*tamper-evident*) berbasis struktur data pohon Merkle (*Merkle tree*) dan teknologi penyimpanan *Write Once Read Many* (WORM).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [ENTERPRISE SECURITY & ZERO-TRUST]
                                           |
         +---------------------------------+---------------------------------+
         |                                 |                                 |
         v                                 v                                 v
[IDENTITY & ACCESS]               [CONTROL & COMPLIANCE]            [ASSURANCE & AUDIT]
  |                                 |                                 |
  +-- Active Directory / LDAP       +-- Zero-Trust Engine             +-- Immutable Logs
  |   (Kerberos, Directory Tree)    |   (NIST SP 800-207 PEP/PDP)     |   (Append-Only, Hash Chain)
  |                                 |                                 |
  +-- Federation Protocols          +-- Fine-Grained Access           +-- Cryptographic Ledger
  |   (SAML 2.0, WS-Fed, OIDC)      |   (RBAC, ABAC, PBAC / OPA)      |   (Merkle Trees, RFC 6962)
  |                                 |                                 |
  +-- Enterprise Directory Sync     +-- Regulatory Baselines          +-- Storage Protections
      (SCIM 2.0, JIT Provisioning)      (FedRAMP High, HIPAA ePHI)        (S3 Object Lock, WORM)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Bagi seorang Forward Deployed Engineer (FDE), kemampuan membangun fitur aplikasi hanyalah setengah dari pertempuran teknis. Medan tempur sebenarnya di lingkungan klien enterprise (*Tier-1 Banks*, penyedia layanan kesehatan, entitas pertahanan, dan agensi federal) terletak pada **lingkungan keamanan, batas kepatuhan, dan integrasi identitas**.

Sebagus apa pun platform analisis data atau kecerdasan buatan yang Anda bawa, sistem tersebut **tidak akan pernah diizinkan beroperasi di lingkungan produksi** jika:
1. Meminta kredensial pengguna lokal alih-alih melakukan federasi ke Microsoft Active Directory / Okta milik klien.
2. Mengabaikan isolasi multi-tenant yang ketat dan gagal membuktikan isolasi hak akses data secara matematis atau terprogram.
3. Melanggar kontrol privasi data (misalnya: mengekspos *Protected Health Information* [ePHI] tanpa enkripsi ujung-ke-ujung yang memenuhi standar HIPAA).
4. Menyediakan log audit yang dapat dimodifikasi atau dihapus oleh administrator lokal (kegagalan total pada audit FedRAMP atau SOC 2 Type II).

FDE beroperasi di garis depan di mana arsitektur perangkat lunak Anda harus "bertabrakan" langsung dengan arsitektur keamanan warisan (*legacy*) milik klien yang sudah berusia puluhan tahun tanpa mengorbankan prinsip postur keamanan modern.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Arsitektur Zero-Trust (NIST SP 800-207)
Paradigma keamanan jaringan yang beroperasi dengan aksioma: *"Never Trust, Always Verify"*. Akses ke sumber daya komputasi tidak pernah diberikan secara implisit hanya berdasarkan lokasi fisik atau jaringan lokal (misal: di balik VPN atau LAN kantor). Setiap permintaan (*request*) harus diautentikasi secara eksplisit, diotorisasi berdasarkan konteks dinamis, dan dienkripsi ujung-ke-ujung.

### 2. Protokol Identitas Enterprise: LDAP vs SAML vs OIDC
* **LDAP (Lightweight Directory Access Protocol)**: Protokol berbasis biner (biasanya port 389 atau 636 untuk LDAPS) yang dirancang untuk membaca dan memodifikasi struktur direktori hierarkis (X.500) seperti Active Directory. Digunakan terutama untuk query internal, autentikasi langsung, dan sinkronisasi server-ke-server.
* **SAML 2.0 (Security Assertion Markup Language)**: Standar terbuka berbasis XML yang memfasilitasi *Single Sign-On* (SSO) berbasis browser antara *Identity Provider* (IdP) dan *Service Provider* (SP). SAML memisahkan otentikasi pengguna dari aplikasi klien melalui penandatanganan kriptografis (*XML Digital Signature*).
* **OIDC (OpenID Connect)**: Lapisan identitas di atas OAuth 2.0 menggunakan format JSON/REST dan JSON Web Tokens (JWT). Menjadi alternatif modern untuk SAML yang dominan pada arsitektur cloud-native dan API modern.

### 3. Model Kontrol Akses: RBAC, ABAC, dan PBAC
* **RBAC (Role-Based Access Control)**: Akses ditentukan oleh peran pengguna (misal: `Auditor`, `Admin`, `Analyst`). Kaku dan rentan terhadap fenomena *Role Explosion*.
* **ABAC (Attribute-Based Access Control)**: Akses dievaluasi dari kombinasi atribut subjek (departemen, sertifikasi), atribut sumber daya (klasifikasi kerahasiaan), dan atribut lingkungan (waktu akses, subnet IP).
* **PBAC (Policy-Based Access Control)**: Otorisasi diekspresikan sebagai kode (*Policy-as-Code*) deklaratif yang dievaluasi secara deterministik oleh mesin independen (misal: Open Policy Agent).

### 4. Lanskap Regulasi: FedRAMP & HIPAA
* **FedRAMP (Federal Risk and Authorization Management Program)**: Standar standardisasi keamanan pemerintah AS untuk produk dan layanan cloud, mengadopsi kontrol NIST SP 800-53. Tingkat *High Baseline* menuntut lebih dari 400 kontrol keamanan ketat, mencakup pemisahan jaringan, enkripsi FIPS 140-2/3, dan audit berkelanjutan.
* **HIPAA Security Rule**: Regulasi kepatuhan kesehatan AS yang mengatur keamanan *Electronic Protected Health Information* (ePHI). Fokus utamanya adalah integritas data, ketersediaan, kontrol akses rahasia (*least privilege*), audit transmisi, dan penghapusan data aman.

### 5. Immutable Audit Trail
Sistem pencatatan log peristiwa yang menjamin sifat *Append-Only* dan integritas kriptografis. Begitu data audit ditulis, data tersebut tidak dapat dimanipulasi, diubah urutannya (*reordered*), atau dihapus bahkan oleh pengguna dengan hak akses *root* atau *DBA*, menggunakan rantai hash (*cryptographic hash chaining*) atau pohon Merkle.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur Autentikasi Federasi SAML 2.0 (SP-Initiated SSO)
1. **Akses Pengguna**: Pengguna mengakses aplikasi web FDE (Service Provider / SP).
2. **SAML AuthnRequest**: SP mendeteksi pengguna belum terotentikasi, membuat payload XML `<samlp:AuthnRequest>`, menandatanganinya dengan sertifikat privat SP, dan me-redirect browser pengguna ke IdP enterprise (misalnya ADFS atau Okta).
3. **Autentikasi di IdP**: Pengguna memasukkan kredensial enterprise (MFA, Active Directory, smartcard PKI).
4. **SAML Assertion Generation**: IdP memverifikasi identitas, menyusun XML `<saml:Assertion>` yang berisi identitas subjek (*NameID*), atribut keanggotaan grup, serta batasan waktu (*NotBefore*, *NotOnOrAfter*). Dokumen ini ditandatangani secara kriptografis menggunakan kunci privat IdP.
5. **Assertion Delivery**: Browser mem-POST assertion tersebut kembali ke endpoint *Assertion Consumer Service* (ACS) milik SP.
6. **Validasi Kriptografis SP**: SP memvalidasi tanda tangan XML menggunakan sertifikat publik IdP yang sudah dipasang sebelumnya, memastikan *issuer*, *audience restriction*, dan masa berlaku assertion.
7. **Pemberian Sesi**: SP mengonversi atribut SAML ke dalam konteks sesi lokal (JWT internal atau sesi terdistribusi Redis) dan memberikan akses.

```
+------------+       1. Get /dashboard        +--------------------+
|            | -----------------------------> |                    |
|            |                                |                    |
|            | 2. Redirect to IdP w/ Request  |                    |
|            | <----------------------------- |                    |
|   Client   |                                |  Service Provider  |
|  Browser   | 5. POST SAML Response (ACS)    |   (FDE Software)   |
|            | -----------------------------> |                    |
|            |                                |                    |
|            | 6. Set Session Cookie / JWT    |                    |
|            | <----------------------------- |                    |
+------------+                                +--------------------+
      |   ^
3.    |   | 4.
Creds |   | SAML Response
      v   |
+--------------------+
|  Enterprise IdP    |
| (Active Directory) |
+--------------------+
```

### Penegakan Kebijakan Zero-Trust: PDP & PEP Architecture
Mengikuti standar arsitektur NIST SP 800-207:
* **PEP (Policy Enforcement Point)**: Komponen di jalur data (*data plane*), seperti API Gateway (Envoy, Kong) atau middleware aplikasi, yang mencegat setiap paket/request masuk dan menunda eksekusi sampai mendapat keputusan dari PDP.
* **PDP (Policy Decision Point)**: Mesin evaluasi aturan (*control plane*), seperti Open Policy Agent (OPA). PDP menerima input berupa atribut pengguna, konteks jaringan, dan sumber daya yang dituju, mengevaluasinya terhadap *Security Policy Repository*, dan mengembalikan keputusan biner: `Allow` atau `Deny`.

### Struktur Immutable Audit Trail Berbasis Merkle Tree
1. Peristiwa audit di-encode sebagai representasi kanonikal JSON.
2. Setiap entri audit di-hash ($H_n = \text{SHA256}(\text{CanonicalEvent}_n)$).
3. Entri dihubungkan secara sekuensial dengan hash sebelumnya ($H_{\text{chain}} = \text{SHA256}(H_n \parallel H_{n-1})$).
4. Pada interval berkala (misal: setiap jam), sekumpulan entri dikonsolidasikan ke dalam struktur *Merkle Tree*. *Merkle Root* yang dihasilkan di-tanda tangani secara kriptografis dan disimpan pada penyimpanan WORM (misal: AWS S3 Object Lock dalam mode *Compliance*) atau di-commit ke public/consortium ledger sebagai bukti eksistensi (*proof of existence*) yang mustahil dipalsukan.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Arsitektur Otorisasi Dinamis Terdistribusi (Zero-Trust PEP/PDP)

```
[ INCOMING TRAFFIC ]
        |
        v
+--------------------------------------------------------------------------+
|                       KUBERNETES INGRESS / API GATEWAY                   |
|                                                                          |
|   +------------------------------------------------------------------+   |
|   |                  POLICY ENFORCEMENT POINT (PEP)                  |   |
|   |                                                                  |   |
|   | 1. Intercept HTTP Request                                        |   |
|   | 2. Extract JWT / Client TLS Cert / Target Resource               |   |
|   | 3. Query PDP via gRPC (Localhost socket / Sidecar)               |   |
|   +------------------------------------------------------------------+   |
+--------------------------------------------------------------------------+
             |                                              ^
             | Context Query (JSON)                         | Auth Decision
             v                                              | (Allow/Deny)
+-----------------------------------------------------------+--------------+
|                         POLICY DECISION POINT (PDP)                      |
|                                                                          |
|   +------------------------------------------------------------------+   |
|   |                 OPEN POLICY AGENT (OPA ENGINE)                   |   |
|   |                                                                  |   |
|   | Evaluates: Target API + User Roles + Tenant Boundaries + Time    |   |
|   +------------------------------------------------------------------+   |
|              ^                                         ^                 |
|              | Pull Policies                           | Pull Data       |
|   +----------------------+                  +------------------------+   |
|   | GitOps Policy Repo   |                  | Directory Service Sync |   |
|   | (Signed Rego Bundles)|                  | (Cached LDAP/SCIM Data)|   |
|   +----------------------+                  +------------------------+   |
+--------------------------------------------------------------------------+
             | (If Decision == ALLOW)
             v
+--------------------------------------------------------------------------+
|                          TARGET MICROSERVICE (APP)                       |
|                                                                          |
|   +------------------------------------------------------------------+   |
|   | Process Business Logic                                           |   |
|   | Generate Immutable Audit Event                                   |   |
|   +------------------------------------------------------------------+   |
+--------------------------------------------------------------------------+
             |
             | Emit Event Payload
             v
+--------------------------------------------------------------------------+
|                       TAMPER-EVIDENT AUDIT PIPELINE                      |
|                                                                          |
|  +--------------------+      +------------------+      +-------------+   |
|  | Append-Only Buffer | ---> | Merkle Tree Root | ---> | S3 WORM Lock|   |
|  | Hash Chaining      |      | Calculation      |      | (Compliance)|   |
|  +--------------------+      +------------------+      +-------------+   |
+--------------------------------------------------------------------------+
```

### 2. Struktur Hash-Chaining & Verifikasi Pohon Merkle

```
Audit Log Chaining (RFC 6962 Model):

  Log Entry 0              Log Entry 1              Log Entry 2
+---------------+        +---------------+        +---------------+
| Event Data 0  |        | Event Data 1  |        | Event Data 2  |
| Prev: 0000000 |        | Prev: Hash 0  |        | Prev: Hash 1  |
+---------------+        +---------------+        +---------------+
        |                        |                        |
        v                        v                        v
   [ Hash 0 ]               [ Hash 1 ]               [ Hash 2 ]
        \                        /                        |
         \                      /                         |
          v                    v                          v
      [ Node 0-1 = H(H0 + H1) ]                     [ Node 2-2 ]
                   \                                     /
                    \                                   /
                     v                                 v
                 [ Merkle Root = H(Node0-1 + Node2-2) ]
                                   |
                  Signed with Private KMS Key
                                   |
                                   v
                 Persisted to Immutable Object Store
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi kebijakan otorisasi deklaratif menggunakan **Open Policy Agent (Rego)**. Kebijakan ini menegakkan aturan bahwa data medis (ePHI) hanya dapat diakses oleh personil berwenang (Dokter/Perawat) yang menangani pasien tersebut secara langsung, dan akses dari luar subnet internal rumah sakit wajib ditolak mentah-mentah.

```rego
# policy/hipaa_authz.rego
package enterprise.security.authz

import future.keywords.in

default allow = false
default audit_required = true

# Konfigurasi Subnet Internal Rumah Sakit yang Diizinkan (CIDR)
trusted_networks := ["10.240.0.0/16", "172.16.50.0/24"]

# Aturan Utama Otorisasi
allow {
    # 1. Autentikasi Identitas Berhasil (JWT valid dan belum expired)
    input.token.valid == true
    
    # 2. Verifikasi Batas Jaringan (Zero-Trust Contextual Verification)
    net.cidr_contains(trusted_networks[_], input.client_ip)
    
    # 3. Evaluasi Hak Akses Khusus Rekam Medis (ePHI)
    user_can_access_medical_record
}

# Logika Otorisasi Berdasarkan Peran & Hubungan (ABAC Model)
user_can_access_medical_record {
    "Clinician" in input.token.roles
    input.request.method == "GET"
    input.request.path = ["patients", patient_id, "medical-records"]
    
    # Pasien harus berada di bawah perawatan dokter yang meminta akses
    patient_id in input.token.assigned_patients
}

user_can_access_medical_record {
    # Administrator Kepatuhan Keamanan (Auditor) hanya boleh membaca log, bukan record mentah
    "ComplianceAuditor" in input.token.roles
    input.request.method == "GET"
    input.request.path = ["patients", _, "audit-trails"]
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah implementasi sistem **Immutable Audit Trail** tingkat produksi menggunakan bahasa Go. Komponen ini menerapkan penautan hash kriptografis (*hash chaining*) secara konkuren, penandatanganan payload, dan penulisan berbasis append-only buffer.

```go
package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"
)

// AuditEvent merepresentasikan payload peristiwa kepatuhan standar FedRAMP/HIPAA.
type AuditEvent struct {
	EventID       string                 `json:"event_id"`
	TimestampNano int64                  `json:"timestamp_nano"`
	ActorID       string                 `json:"actor_id"`
	Action        string                 `json:"action"`
	ResourceID    string                 `json:"resource_id"`
	Metadata      map[string]interface{} `json:"metadata"`
	PrevHash      string                 `json:"prev_hash"`
	CurrentHash   string                 `json:"current_hash"`
}

// ImmutableAuditLedger mengelola rantai blok audit dengan sinkronisasi thread-safe.
type ImmutableAuditLedger struct {
	mu        sync.RWMutex
	secretKey []byte
	lastHash  string
	storage   []AuditEvent
}

// NewImmutableLedger menginisialisasi ledger dengan Genesis Hash.
func NewImmutableLedger(secretKey []byte) *ImmutableAuditLedger {
	// Genesis Hash diinisialisasi menggunakan initial seed SHA-256
	initialSeed := sha256.Sum256([]byte("GENESIS_ZERO_TRUST_AUDIT_TRAIL"))
	return &ImmutableAuditLedger{
		secretKey: secretKey,
		lastHash:  hex.EncodeToString(initialSeed[:]),
		storage:   make([]AuditEvent, 0),
	}
}

// calculateHash menghitung HMAC-SHA256 dari representasi kanonikal event.
func (l *ImmutableAuditLedger) calculateHash(event AuditEvent) (string, error) {
	// Salin objek untuk mengosongkan hash saat penghitungan
	canonical := struct {
		EventID       string                 `json:"event_id"`
		TimestampNano int64                  `json:"timestamp_nano"`
		ActorID       string                 `json:"actor_id"`
		Action        string                 `json:"action"`
		ResourceID    string                 `json:"resource_id"`
		Metadata      map[string]interface{} `json:"metadata"`
		PrevHash      string                 `json:"prev_hash"`
	}{
		EventID:       event.EventID,
		TimestampNano: event.TimestampNano,
		ActorID:       event.ActorID,
		Action:        event.Action,
		ResourceID:    event.ResourceID,
		Metadata:      event.Metadata,
		PrevHash:      event.PrevHash,
	}

	rawBytes, err := json.Marshal(canonical)
	if err != nil {
		return "", err
	}

	mac := hmac.New(sha256.New, l.secretKey)
	mac.Write(rawBytes)
	return hex.EncodeToString(mac.Sum(nil)), nil
}

// RecordEvent menambahkan peristiwa baru ke rantai secara atomik.
func (l *ImmutableAuditLedger) RecordEvent(actorID, action, resourceID string, meta map[string]interface{}) (AuditEvent, error) {
	l.mu.Lock()
	defer l.mu.Unlock()

	event := AuditEvent{
		EventID:       fmt.Sprintf("evt_%d", time.Now().UnixNano()),
		TimestampNano: time.Now().UnixNano(),
		ActorID:       actorID,
		Action:        action,
		ResourceID:    resourceID,
		Metadata:      meta,
		PrevHash:      l.lastHash,
	}

	computedHash, err := l.calculateHash(event)
	if err != nil {
		return AuditEvent{}, fmt.Errorf("failed calculating cryptographic audit hash: %w", err)
	}

	event.CurrentHash = computedHash
	
	// Mutasi pointer ledger
	l.lastHash = computedHash
	l.storage = append(l.storage, event)

	return event, nil
}

// VerifyIntegrity memvalidasi seluruh rantai log dari awal hingga akhir.
func (l *ImmutableAuditLedger) VerifyIntegrity() (bool, error) {
	l.mu.RLock()
	defer l.mu.RUnlock()

	expectedPrevHash := hex.EncodeToString(sha256.New().Sum([]byte("GENESIS_ZERO_TRUST_AUDIT_TRAIL")))
	// Inisialisasi hash genesis ulang
	seed := sha256.Sum256([]byte("GENESIS_ZERO_TRUST_AUDIT_TRAIL"))
	expectedPrevHash = hex.EncodeToString(seed[:])

	for i, entry := range l.storage {
		// 1. Periksa rantai hash pointer
		if entry.PrevHash != expectedPrevHash {
			return false, fmt.Errorf("audit chain broken at index %d: invalid prev_hash linkage", i)
		}

		// 2. Kalkulasi ulang integritas hash
		recomputedHash, err := l.calculateHash(entry)
		if err != nil {
			return false, fmt.Errorf("error during recomputation at index %d: %w", i, err)
		}

		if entry.CurrentHash != recomputedHash {
			return false, fmt.Errorf("tamper detected at index %d: data hash mismatch", i)
		}

		expectedPrevHash = entry.CurrentHash
	}

	return true, nil
}

func main() {
	secretKey := []byte("fde-production-enterprise-secret-key-32b")
	ledger := NewImmutableLedger(secretKey)

	fmt.Println("[SECURITY] Menginisialisasi Append-Only Immutable Audit Log...")

	// 1. Simulasikan Penulisan Log Normal
	e1, _ := ledger.RecordEvent("usr_dr_smith", "VIEW_EPHI", "rec_patient_90210", map[string]interface{}{
		"client_ip": "10.240.12.44",
		"reason":    "Emergency Consult",
	})
	fmt.Printf("[AUDIT LOG %s] Recorded: %s | Hash: %s\n", e1.EventID, e1.Action, e1.CurrentHash)

	e2, _ := ledger.RecordEvent("usr_dr_smith", "MODIFY_PRESCRIPTION", "rec_patient_90210", map[string]interface{}{
		"dosage": "500mg Amoxicillin",
	})
	fmt.Printf("[AUDIT LOG %s] Recorded: %s | Hash: %s\n", e2.EventID, e2.Action, e2.CurrentHash)

	// 2. Uji Verifikasi Keabsahan Log
	valid, err := ledger.VerifyIntegrity()
	if err != nil || !valid {
		fmt.Printf("[INTEGRITY CHECK] FAILED: %v\n", err)
	} else {
		fmt.Println("[INTEGRITY CHECK] SUCCESS: Seluruh rantai audit valid dan bebas manipulasi.")
	}

	// 3. Simulasikan Upaya Pemalsuan Data Log (Tampering Attack)
	fmt.Println("\n[ATTACK SIMULATION] Mengubah record audit secara ilegal di memori...")
	ledger.storage[0].ActorID = "usr_malicious_attacker"

	// 4. Verifikasi Ulang Setelah Serangan
	validAfterAttack, attackErr := ledger.VerifyIntegrity()
	if !validAfterAttack {
		fmt.Printf("[INTEGRITY CHECK] CRITICAL ALERT: Integritas log terkompromi! Detail: %v\n", attackErr)
	}
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Aspek / Solusi | Pendekatan A | Pendekatan B | Analisis Trade-off FDE |
| :--- | :--- | :--- | :--- |
| **Model Otorisasi** | **RBAC (Role-Based)**<br>Peran statis (Admin, Editor). | **ABAC / PBAC (Rego)**<br>Evaluasi atribut dan konteks dinamis. | RBAC mudah diimplementasikan dan di-cache, namun rentan mengalami *role explosion* di enterprise besar. ABAC/PBAC menawarkan keamanan Zero-Trust murni, namun memperkenalkan beban komputasi dan latensi pada throughput API tinggi. |
| **Integrasi Identitas** | **Direct LDAP Sync**<br>Query langsung ke AD DC. | **SAML 2.0 / OIDC Federation**<br>Federasi token melalui IdP. | Sambungan LDAP memerlukan pembukaan firewall port biner internal (LDAPS 636) ke Active Directory dan sering kali ditolak tim infosec klien. SAML/OIDC sepenuhnya berbasis web/HTTPS, tetapi menuntut setup Trust Relationship sertifikat yang kompleks. |
| **Audit Storage** | **Relational DB w/ Triggers**<br>PostgreSQL tabel append-only. | **WORM Cloud Object Lock**<br>S3 Object Lock (Compliance Mode). | Relational DB sangat cepat untuk pencarian kueri kompleks menggunakan SQL, namun seorang sysadmin dengan akses `postgres` dapat merekayasa data. WORM S3 memiliki latensi tulis lebih lambat dan query kaku, namun memberikan jaminan legal terhadap kepatuhan FedRAMP/HIPAA. |
| **Policy Evaluation** | **Embedded Library (In-Process)**<br>Mengevaluasi OPA langsung di memori aplikasi Go/Java. | **Sidecar / Centralized PDP**<br>Mengakses PDP via gRPC/HTTP lokal atau remote. | *Embedded* memiliki overhead latensi nyaris nol (<1ms), tetapi memperbarui kebijakan mengharuskan *reload* proses aplikasi. *Sidecar/Remote* memisahkan siklus hidup kebijakan dari kode aplikasi, tetapi menambah latensi jaring (*network hop*). |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan SCIM 2.0 untuk Sinkronisasi Identitas**: Hindari melakukan polling LDAP secara berkala yang membebani Domain Controller enterprise. Gunakan *System for Cross-domain Identity Management* (SCIM) agar IdP klien (Okta, Azure AD) secara otomatis melakukan *push* mutasi pengguna (buat, ubah, nonaktifkan) secara real-time.
2. **Kriptografi FIPS 140-2/3 Validated**: Ketika men-deploy sistem untuk klien bersertifikasi FedRAMP, aplikasi Go/Rust Anda wajib dikompilasi menggunakan modul kriptografi yang tervalidasi FIPS (misal: BoringCrypto untuk Go: `GOEXPERIMENT=systemcrypto` atau `CGO_ENABLED=1` dengan OpenSSL FIPS provider).
3. **Pemisahan Kunci Audit Melalui Envelope Encryption**: Lindungi integritas log audit menggunakan *Key Management Service* (AWS KMS, HashiCorp Vault, atau Azure Key Vault). Gunakan *Data Encryption Key* (DEK) unik untuk setiap batch log audit dan enkripsi DEK tersebut menggunakan *Key Encryption Key* (KEK) yang memiliki proteksi rotasi otomatis.
4. **Prinsip Least-Functionality (NIST SP 800-70)**: Hilangkan seluruh binari, shell, dan alat debugging (curl, bash, netcat) dari kontainer produksi (*distroless container image*). Ini secara drastis mengurangi vektor serangan jika terjadi *Remote Code Execution* (RCE).
5. **Fail-Closed Default**: Jika sistem evaluasi otorisasi (PDP) mengalami kegagalan komunikasi (*timeout* atau *unreachable*), sistem **wajib** menolak akses (*Deny All*), bukan meloloskan permintaan demi ketersediaan (*availability*).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **XML Signature Wrapping (XSW) Vulnerability pada SAML**: Memvalidasi integritas tanda tangan digital SAML, tetapi mengambil data atribut pengguna dari node XML yang tidak ditandatangani (*unsigned nodes*). Penyerang dapat menyuntikkan pernyataan XML palsu di luar elemen yang divalidasi.
   * *Remediasi*: Gunakan pustaka SAML enterprise yang teruji ketat (seperti `crewjam/saml`) yang secara otomatis menolak payload XML dengan struktur multi-assertion ambigu.
2. **Mengekspos ePHI/PII di Dalam Payload Audit Log**: Menuliskan data rekam medis, nomor jaminan sosial, atau kunci rahasia secara transparan ke dalam pesan audit (*audit message text*). Hal ini melanggar HIPAA Security Rule karena audit trail itu sendiri menjadi subjek kebocoran data.
   * *Remediasi*: Terapkan *data masking*, hashing satu arah, atau simpan hanya referensi ID sumber daya (`ResourceID: "pat_98124"`), bukan representasi datanya.
3. **Clock Skew Ignorance**: Mengabaikan sinkronisasi waktu NTP di antara node server aplikasi dan IdP klien. Deviasi waktu beberapa detik saja dapat menyebabkan validasi assertion SAML (`NotBefore` / `NotOnOrAfter`) atau token OIDC ditolak secara sporadis di lingkungan produksi.
4. **Mencampur Log Telemetri dengan Log Audit Kepatuhan**: Menggabungkan log debug teknis (misal: "Database connection reconnected") dengan log audit bisnis legal (misal: "User X export 5000 medical records"). Hal ini menyebabkan log kepatuhan sulit dipertahankan dalam retensi jangka panjang (HIPAA menuntut retensi 6 tahun).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Validasi XML Digital Signature Assertion SAML (Go)
**Tantangan**: Buat sebuah fungsi verifikasi dalam Go yang menerima string XML SAML Response dan sertifikat publik X.509 IdP. Fungsi harus memverifikasi bahwa tanda tangan digital XML valid, *timestamp* belum kedaluwarsa, dan audiens sesuai dengan entitas SP Anda. Jika validasi gagal, kembalikan galat deskriptif.

### Latihan 2: Implementasi Merkle Tree Audit Batching
**Tantangan**: 
1. Buat sistem yang mengumpulkan 100 entri log ke dalam sebuah batch.
2. Buat struktur data *Merkle Tree* dari ke-100 entri tersebut.
3. Cetak *Merkle Root* ke konsol.
4. Buat fungsi *Merkle Proof* yang dapat membuktikan bahwa entri log ke-42 memang benar-benar ada di dalam pohon Merkle tersebut tanpa harus membaca 99 entri lainnya.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Mengapa SAML 2.0 WebSSO lebih disukai oleh tim keamanan enterprise daripada mengizinkan aplikasi FDE meminta kredensial username/password Active Directory secara langsung?**
   * A. Karena SAML 2.0 berbasis JSON sehingga parsing-nya lebih cepat dari protokol biner LDAP.
   * B. Karena aplikasi FDE tidak pernah menyentuh, melihat, atau menyimpan password pengguna secara langsung, mencegah kebocoran kredensial terpusat.
   * C. Karena SAML 2.0 tidak memerlukan konfigurasi Public Key Infrastructure (PKI).
   * D. Karena SAML 2.0 mengizinkan akses administratif penuh tanpa audit.
   * *Jawaban yang Benar: B*. Federasi identitas memutus kebutuhan aplikasi pihak ketiga untuk mengetahui *master password* enterprise; IdP melakukan autentikasi sendiri dan hanya memberikan *signed assertion* kepada SP.

2. **Dalam implementasi Zero-Trust berbasis NIST SP 800-207, di manakah posisi Envoy Proxy yang mencegat trafik API mikroservis?**
   * A. Policy Decision Point (PDP).
   * B. Policy Administration Point (PAP).
   * C. Policy Enforcement Point (PEP).
   * D. Identity Provider (IdP).
   * *Jawaban yang Benar: C*. Proxy bertindak sebagai PEP di jalur data (*data plane*), bertugas mencegat trafik dan meminta otorisasi ke PDP sebelum meneruskannya ke backend.

3. **Kontrol spesifik apa yang membedakan penyimpanan WORM (Write Once Read Many) dari sistem backup basis data relasional biasa dalam kepatuhan FedRAMP High?**
   * A. WORM menjamin latensi tulis di bawah 1 milidetik.
   * B. WORM menerapkan penguncian berbasis hardware/software yang membatalkan perintah penghapusan/modifikasi berkas secara absolut, bahkan oleh akun super-administrator (root) hingga masa retensi legal berakhir.
   * C. WORM menggunakan algoritma kompresi gzip multi-thread.
   * D. WORM mengharuskan enkripsi kunci publik RSA-1024.
   * *Jawaban yang Benar: B*. WORM (seperti AWS S3 Object Lock dalam mode Compliance) secara eksplisit mencegah penghapusan file oleh siapa pun sebelum periode retensi berakhir demi memastikan integritas hukum data audit.

4. **Kelemahan fatal apa yang terjadi jika penautan hash log audit (*hash-chaining*) dihitung tanpa menyertakan secret key bersama (HMAC) atau tanpa tanda tangan asimetris?**
   * A. Log akan mengalami korupsi data saat disimpan di disk SSD.
   * B. Penyerang yang berhasil menyusupi server dapat memanipulasi data di baris tengah dan dengan mudah menghitung ulang seluruh nilai hash ke depan secara mandiri (*hash recomputation*).
   * C. Throughput komputasi hash menjadi 100 kali lebih lambat.
   * D. Log tidak dapat dibaca oleh OPA.
   * *Jawaban yang Benar: B*. Plain SHA-256 hash chaining dapat dihitung ulang dengan mudah oleh siapa saja yang memegang data mentah. Penambahan HMAC dengan kunci rahasia atau digital signature memastikan hanya pihak terotorisasi yang dapat menghasilkan hash yang sah.

5. **Di bawah aturan HIPAA Security Rule, berapa lama data audit trail yang mencatat akses terhadap ePHI wajib disimpan dan dapat ditelusuri kembali?**
   * A. 30 Hari.
   * B. 1 Tahun.
   * C. 6 Tahun.
   * D. Seumur hidup sistem.
   * *Jawaban yang Benar: C*. HIPAA administrative simplification regulations (45 CFR § 164.316(b)(2)) mewajibkan dokumentasi kebijakan, prosedur, dan log audit tindakan terkait disimpan minimal selama 6 tahun sejak tanggal pembuatannya.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **NIST Special Publication 800-207**: *Zero Trust Architecture* (National Institute of Standards and Technology).
* **NIST Special Publication 800-53 (Rev 5)**: *Security and Privacy Controls for Information Systems and Organizations* (Dasar Kepatuhan FedRAMP).
* **RFC 6962**: *Certificate Transparency* (Fondasi teknis implementasi Append-Only Merkle Tree Log).
* **Open Policy Agent (OPA) Documentation**: *Policy-based Control for Cloud Native Environments* (`https://www.openpolicyagent.org/docs/`).
* **U.S. Department of Health and Human Services (HHS)**: *Guidance on HIPAA Security Rule Compliance and ePHI Safeguards*.
* **OASIS Security Services (SAML) TC**: *Profiles for the OASIS Security Assertion Markup Language (SAML) V2.0*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

Modul ini telah membedah arsitektur keamanan tingkat tinggi yang menjadi syarat mutlak keberhasilan seorang Forward Deployed Engineer di medan operasional enterprise:
1. **Zero-Trust**: Tidak ada lagi perimeter terpercaya; validasi identitas dan konteks dievaluasi secara dinamis pada setiap panggilan API menggunakan arsitektur PEP/PDP.
2. **Federasi Identitas Enterprise**: Menjembatani dunia on-premise warisan (Active Directory, Kerberos, LDAP) dan arsitektur web modern melalui protokol SAML 2.0 dan OIDC tanpa mengekspos kredensial rahasia pengguna.
3. **Otorisasi Granular**: Transisi dari model peran kaku (RBAC) ke *Policy-as-Code* (ABAC/PBAC) menggunakan Open Policy Agent yang deterministik dan dapat diuji secara independen.
4. **Kepatuhan Regulasi (FedRAMP & HIPAA)**: Memastikan isolasi data, enkripsi tingkat FIPS, dan kontrol operasional yang ketat untuk data berklasifikasi tinggi (PII/ePHI).
5. **Integritas Audit Nir-Ubah**: Membangun mekanisme pencatatan data peristiwa audit anti-tamper melalui hash-chaining, Merkle Trees, dan media penyimpanan berbasis WORM.

---

## SEKSI 17 — GLOSARIUM

* **Assertion Consumer Service (ACS)**: Endpoint URL pada Service Provider (SP) yang bertugas menerima, mem-parse, dan memvalidasi token SAML Response dari Identity Provider.
* **Envelope Encryption**: Skema kriptografi di mana data dienkripsi dengan kunci simetris lokal (*Data Key*), dan *Data Key* tersebut kemudian dienkripsi oleh kunci master terpusat (*Key Encryption Key*).
* **FIPS 140-2/3**: Standar akreditasi keamanan komputer pemerintah AS yang digunakan untuk menyetujui modul kriptografi.
* **Hash-Chaining**: Teknik kriptografi di mana hash blok data saat ini memasukkan nilai hash dari blok data sebelumnya ke dalam perhitungannya, menciptakan rantai ketergantungan yang tidak dapat diubah.
* **Immutable Storage (WORM)**: Teknologi media penyimpanan data yang memungkinkan penulisan data hanya sekali dan mencegah penulisan ulang, modifikasi, atau penghapusan selama periode waktu yang ditentukan (*Write Once, Read Many*).
* **Merkle Root**: Hash puncak dari sebuah pohon biner kriptografis (*Merkle Tree*) yang merangkum integritas seluruh daun (*leaf nodes*) di bawahnya.
* **Policy Enforcement Point (PEP)**: Titik logis dalam arsitektur keamanan yang mencegat permintaan akses pengguna ke sumber daya dan menegakkan keputusan dari PDP.
* **Policy Decision Point (PDP)**: Entitas logis yang mengevaluasi kebijakan otorisasi terhadap atribut subjek dan konteks untuk mengeluarkan keputusan akses (*Allow/Deny*).
* **SCIM (System for Cross-domain Identity Management)**: Protokol berbasis REST/JSON standar terbuka untuk mengotomatisasi provisi dan deprovisi akun pengguna antar sistem identitas yang berbeda.
* **XML Signature Wrapping (XSW)**: Kerentanan keamanan di mana penyerang memanipulasi struktur XML untuk mengelabui verifikator agar memvalidasi tanda tangan pada blok asli, namun mengeksekusi blok tiruan yang disisipkan.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Tantangan Lapangan (Air-Gapped Environments)**: Berikan penekanan kepada peserta bahwa di lingkungan pertahanan atau intelijen, sistem sering kali berjalan tanpa koneksi internet sama sekali (*air-gapped*). Validasi CRL (*Certificate Revocation List*) atau OCSP secara online tidak akan bekerja; instruksikan peserta cara mengonfigurasi trust chain X.509 dengan bundle sertifikat lokal dan pembaruan CRL berbasis volume mount.
* **Fokus Audit Log**: Pastikan peserta memahami perbedaan kritis antara log aplikasi fungsional (stdout/stderr) dan log audit kepatuhan. Log audit harus memiliki jalur pipa (*pipeline*) khusus yang terisolasi dari kegagalan sistem log biasa (misalnya: jika disk penuh, apakah aplikasi harus berhenti (*fail-closed*) demi mematuhi FedRAMP?).
* **Laboratorium Hands-on**: Gunakan simulasi containerized open-source IdP (seperti Keycloak) di Docker Compose lokal agar peserta dapat mempraktikkan konfigurasi SP metadata dan sertifikat penandatanganan tanpa perlu mengakses instans Azure AD atau Active Directory produksi yang sesungguhnya.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: 1.0.0
* **Tanggal Rilis**: 2025-01-15
* **Author**: Senior Technical Curriculum Architect (Enterprise & Security Domain)
* **Catatan Perubahan**:
  * Rilis inisial standar kurikulum Forward Deployed Engineer (FDE).
  * Penambahan arsitektur Zero-Trust NIST SP 800-207 mendalam.
  * Penyediaan contoh kode audit ledger append-only lengkap berbasis Go dengan verifikasi HMAC.
  * Penyusunan aturan kebijakan deklaratif Rego untuk HIPAA compliance.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `FDE-ARCH-0402: Resilience, Circuit Breaking, Fault Tolerance & Chaos Engineering`
* **Modul Saat Ini**: `FDE-ARCH-0501: Keamanan Enterprise, Zero-Trust & Kepatuhan Regulasi`
* **Modul Berikutnya**: `FDE-ARCH-0502: Air-Gapped Deployments, Edge Computing & Data Sovereign Networks`