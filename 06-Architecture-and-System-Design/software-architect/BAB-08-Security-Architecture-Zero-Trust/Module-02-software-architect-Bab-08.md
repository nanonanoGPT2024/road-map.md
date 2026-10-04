# BAB 08: Security Architecture & Zero Trust
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mendesain dan Mengimplementasikan Arsitektur Zero Trust (ZTA)** berbasis standar NIST SP 800-207 secara menyeluruh pada ekosistem komputasi terdistribusi skala enterprise.
2. **Memisahkan Control Plane dan Data Plane** secara tegas melalui orkestrasi *Policy Enforcement Point* (PEP), *Policy Decision Point* (PDP), *Policy Information Point* (PIP), dan *Policy Administration Point* (PAP).
3. **Mengonfigurasi dan Memvalidasi Identitas Kriptografis Bebas State (Stateless/Ephemeral)** menggunakan spesifikasi SPIFFE/SPIRE untuk komunikasi machine-to-machine (M2M) dengan rotasi otomatis sertifikat X.509 SVID.
4. **Membangun Dynamic Authorization Engine Berkinerja Tinggi** menggunakan Open Policy Agent (OPA) terintegrasi Envoy Proxy melalui protokol gRPC `ext_authz` dengan latensi evaluasi sub-milidetik.
5. **Mengimplementasikan Microsegmentation Lanjutan** pada layer L4/L7 menggunakan eBPF dan Service Mesh untuk mengisolasi *blast radius* insiden keamanan siber.
6. **Mengevaluasi Trade-off Teknis** antara postur keamanan ketat (*fail-closed* vs *fail-open*), latensi komputasi kriptografis, konsumsi resource CPU/memori, dan kompleksitas operasional infrastruktur multi-region.

---

### 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut sebelum mempelajari modul ini:
* **Kriptografi Terapan**: Pemahaman mendalam tentang Asymmetric Cryptography, Public Key Infrastructure (PKI), TLS 1.3 handshake, Mutual TLS (mTLS), X.509 certificate parsing, dan Elliptic Curve Cryptography (ECDSA/Ed25519).
* **Jaringan Komputer Lanjutan**: Pemahaman mendalam tentang OSI Layer 4 (TCP state machine, socket reuse) dan Layer 7 (HTTP/2 multiplexing, gRPC streaming, header inspection), routing iptables, serta dasar manipulasi kernel packet flow via eBPF/XDP.
* **Sistem Terdistribusi**: Pemahaman pola desain *reverse proxy/sidecar*, arsitektur service mesh (Envoy, Istio), dan konsensus terdistribusi (Raft/etcd).
* **Bahasa Pemrograman & Tooling**: Kemahiran membaca dan menulis kode Go (Golang) tingkat menengah-lanjut, sintaks declarative YAML, serta dasar logika deklaratif Datalog/Rego.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi Zero Trust Architecture (ZTA) tingkat produksi menggeser paradigma keamanan dari batas perimeter berbasis jaringan (IP/subnet) menjadi batas perimeter berbasis identitas dan konteks kriptografis (*Identity-based Boundary*). 

Mengacu pada arsitektur formal **NIST SP 800-207**, arsitektur sistem Zero Trust dibagi menjadi dua domain fungsional: **Control Plane** dan **Data Plane**.

```
+-----------------------------------------------------------------------------------+
| CONTROL PLANE                                                                     |
|                                                                                   |
|  +--------------------+         +-----------------------------------------------+ |
|  |  PAP               |         |  PDP (Policy Decision Point)                  | |
|  | (Policy Admin Pt)  |         |                                               | |
|  | GitOps / CI-CD     |=======> |  +------------------+   +-------------------+ | |
|  | Rego Policy Repo   |         |  | Rule Engine      |   | Trust Engine      | | |
|  +--------------------+         |  | (OPA Daemon)     |   | (Dynamic Risk)    | | |
|                                 |  +------------------+   +-------------------+ | |
|                                 +--------^-------------------------^------------+ |
|                                          |                         |              |
|                                          | Query                   | Fetch Data   |
|                                          v                         v              |
|                                 +-----------------------------------------------+ |
|                                 |  PIP (Policy Information Point)               | |
|                                 |  - Identity Provider (IdP/OIDC)               | |
|                                 |  - Device Posture (MDM API)                   | |
|                                 |  - Threat Intelligence / SIEM                 | |
|                                 |  - SPIRE Server (Workload Attestation)        | |
|                                 +-----------------------------------------------+ |
+------------------------------------------|----------------------------------------+
                                           | Decision Response (gRPC ext_authz)
                                           v
+-----------------------------------------------------------------------------------+
| DATA PLANE                                                                        |
|                                                                                   |
|    Inbound Request               PEP (Policy Enforcement Point)                   |
|  ===================> [ Envoy Proxy / Sidecar / eBPF Filter ]                     |
|                       |                                                           |
|                       +--- (1) Intercept L7/L4 Packet                             |
|                       +--- (2) Extract Context (SPIFFE ID, JWT, Client TLS, IP)   |
|                       +--- (3) Query PDP via Local Socket / gRPC                  |
|                       +--- (4) If ALLOW -> Forward Payload to Service Container   |
|                       +--- (5) If DENY  -> Terminate TLS, Emit RFC 7807 JSON Error |
|                                          |                                        |
|                                          v                                        |
|                             +--------------------------+                          |
|                             | Upstream Target Workload |                          |
|                             | (Microservice/Database)  |                          |
|                             +--------------------------+                          |
+-----------------------------------------------------------------------------------+
```

#### Komponen Inti NIST SP 800-207:
1. **PEP (Policy Enforcement Point)**: Komponen Data Plane yang bertugas mencegat, memeriksa, dan memutus atau meneruskan koneksi jaringan antara subjek (klien/servis asal) dan objek (sumber daya tujuan). Biasanya diimplementasikan sebagai Envoy reverse-proxy, eBPF socket filter, atau Ingress Gateway.
2. **PDP (Policy Decision Point)**: Komponen Control Plane yang bertindak sebagai mesin komputasi keputusan. PDP menerima konteks permintaan dari PEP, mengevaluasi aturan bisnis dan keamanan, kemudian mengeluarkan keputusan deterministik (`ALLOW`, `DENY`, atau `CHALLENGE`).
3. **PIP (Policy Information Point)**: Sumber data kontekstual eksternal yang di-query oleh PDP untuk melengkapi evaluasi akses. Termasuk di dalamnya: Status kepatuhan perangkat (MDM), histori anomali perilaku (UEBA), identitas pengguna (IdP), dan metadata beban kerja.
4. **PAP (Policy Administration Point)**: Antarmuka otoritatif tempat aturan keamanan didefinisikan, diuji, dan dipublikasikan. Dalam paradigma modern, PAP berbentuk repositori Git yang dikelola melalui pola GitOps dengan pipeline verifikasi formal.

#### SPIFFE/SPIRE: The Cryptographic Identity Spine
Zero Trust mengeliminasi ketergantungan pada IP Address sebagai basis identitas servis karena sifat IP yang dinamis, mudah di-*spoofing*, dan tidak merefleksikan identitas beban kerja (*workload*). Sebagai gantinya, standar **SPIFFE (Secure Production Identity Framework for Everyone)** digunakan untuk memberikan identitas kriptografis berbasis URI:
$$\text{spiffe://trust-domain/ns/production/sa/payment-service}$$

**SPIRE (SPIFFE Runtime Environment)** mengimplementasikan spesifikasi ini melalui dua komponen:
* **SPIRE Server**: Menjaga integritas *Trust Domain*, menerbitkan sertifikat X.509 SVID (SPIFFE Verifiable Identity Document), dan mengesahkan (*attest*) identitas SPIRE Node Agent.
* **SPIRE Agent**: Berjalan sebagai daemonset lokal pada host/node. Agent melakukan **Node Attestation** (memvalidasi integritas VM/OS host via AWS IID, GCP GCE Attestation, atau TPM) dan **Workload Attestation** (memeriksa kernel metadata beban kerja lokal seperti Linux cgroups, systemd unit, namespace, atau Kubernetes Service Account UID).
* **Workload API**: UNIX Domain Socket lokal (`/run/spire/sockets/agent.sock`) yang diekspos oleh Agent ke pod/aplikasi lokal. Aplikasi atau Envoy Sidecar dapat mengambil sertifikat mTLS X.509 tanpa perlu memegang private key statis di disk, mencegah risiko kebocoran credential pada *storage snapshot*.

#### OPA Engine (Open Policy Agent) & Envoy Integration
PDP berkinerja tinggi dibangun menggunakan OPA yang ditautkan langsung dengan Envoy melalui protokol gRPC **Envoy External Authorization (ext_authz)** API. 
* PEP (Envoy) mengekstraksi metadata L7 (URI path, method, headers, TLS Client Certificate Subject Alternative Name) dan membungkusnya ke dalam struktur `CheckRequest`.
* Permintaan diteruskan ke OPA melalui shared Unix Domain Socket (UDS) atau koneksi loopback TCP lokal dengan *keep-alive*.
* OPA mengevaluasi aturan yang ditulis dalam bahasa deklaratif **Rego**, menghasilkan status `OK` (HTTP 200) atau `PERMISSION_DENIED` (HTTP 403) beserta mutasi header tambahan yang diinjeksikan ke upstream (*dynamic claims injection*).

---

### 4. Why & What

#### Kegagalan Model Perimeter Tradisional ("Castle and Moat")
Pada arsitektur jaringan tradisional, perimeter dibatasi oleh firewall berbasis zona (*Demilitarized Zone* / DMZ). Semua entitas di dalam perimeter diasumsikan tepercaya (*implicit trust*). Ketika penyerang menembus perimeter melalui teknik *Spear Phishing*, *Software Vulnerability (RCE)*, atau *Compromised VPN Credentials*, penyerang memiliki kapabilitas untuk melakukan pergerakan lateral (*lateral movement*) tanpa hambatan ke seluruh segmen infrastruktur internal.

| Aspek | Arsitektur Perimeter Klasik | Arsitektur Zero Trust (ZTA) Produksi |
| :--- | :--- | :--- |
| **Model Kepercayaan** | *Implicit Trust* berbasis lokasi jaringan (IP/Subnet) | *Zero Implicit Trust*; Verifikasi terus-menerus (*Continuous Verification*) |
| **Identitas Beban Kerja** | Alamat IP, VPC Peering, Security Group statis | SPIFFE ID Kriptografis, Ephemeral mTLS X.509 SVID |
| **Otorisasi Akses** | Akses coarse-grained pada firewall (Port/IP rules) | Fine-grained L7 Attribute-Based Access Control (ABAC) |
| **Waktu Hidup Kredensial** | Statis (API Keys, Long-lived JWT, SSH Keys tahunan) | Ephemeral (Rotasi otomatis dalam hitungan jam/menit) |
| **Batas Blast Radius** | Luas (Seluruh subnet/VPC internal terdampak) | Mikro (Terisolasi per-workload via microsegmentation) |
| **Audit & Visibilitas** | Log L4 terfragmentasi pada router/firewall | Immutable cryptographic audit trail pada layer L7 |

#### Postur Keamanan Zero Trust: Tiga Pilar Operasional
1. **Verify Explicitly**: Selalu lakukan autentikasi dan otorisasi berdasarkan seluruh titik data yang tersedia, termasuk identitas pengguna, identitas beban kerja, status perangkat, lokasi geografis, klasifikasi data, dan deteksi anomali.
2. **Use Least Privilege Access**: Batasi akses pengguna dan beban kerja menggunakan teknik *Just-In-Time* (JIT) dan *Just-Enough-Access* (JEA), dikombinasikan dengan kebijakan adaptif dinamis.
3. **Assume Breach**: Minimalkan *blast radius* dengan melakukan enkripsi end-to-end (mTLS), segmentasi jaringan mikro, verifikasi postur runtime terus menerus, dan instrumentasi observabilitas real-time.

---

### 5. How (Workflow Detail)

Berikut adalah workflow eksekusi Zero Trust end-to-end saat sebuah microservice memanggil endpoint pembayaran:

```
[Service A: Checkout]          [Envoy Sidecar PEP]              [SPIRE Agent]           [OPA PDP Service]         [Service B: Payment]
         |                              |                              |                        |                          |
         |-- (1) Fetch TLS Identity --->|                              |                        |                          |
         |    via Workload API          |-- (2) Fetch X.509 SVID ----->|                        |                          |
         |                              |<- (3) Return SVID (SAN) -----|                        |                          |
         |                              |                                                       |                          |
         |-- (4) HTTP POST /v1/charge ->|                                                       |                          |
         |    (Bearer Token + Data)     |-- (5) Intercept Packet                                |                          |
         |                              |-- (6) Formulate CheckRequest (gRPC) ----------------->|                          |
         |                              |       - Method: POST, Path: /v1/charge                |                          |
         |                              |       - Client SAN: spiffe://prod/sa/checkout         |-- (7) Evaluate Rego       |
         |                              |       - Headers: Authorization, Device-State          |    - Validate SAN match  |
         |                              |                                                       |    - Verify JWT exp/sig  |
         |                              |                                                       |    - Fetch PIP Posture   |
         |                              |                                                       |    - Risk Assessment <=2 |
         |                              |<- (8) CheckResponse (ALLOW + Inject Trace-Context) ---|                          |
         |                              |                                                                                  |
         |                              |-- (9) Establish mTLS (TLS 1.3, ECDSA) ------------------------------------------>|
         |                              |       Forward Request with Signed Identity Headers                               |
         |                              |                                                                                  |-- (10) Process Logic
         |                              |<- (11) Return 200 OK Encrypted Payload ------------------------------------------|
         |<- (12) Return HTTP 200 OK ---|
```

#### Langkah-Langkah Operasional:
1. **Bootstrapping Workload Identity**:
   * Saat kontainer `Checkout` melakukan booting, SPIRE Agent menginterogasi Linux kernel API (`/proc/$PID/cgroup`) untuk memverifikasi atribut pod.
   * SPIRE Agent membandingkan *workload selector* dengan entri registrasi di SPIRE Server. Jika terbukti valid, SPIRE Agent menerbitkan sertifikat SVID X.509 yang disimpan secara in-memory melalui Envoy Secret Discovery Service (SDS).
2. **Packet Interception & L7 Extraction**:
   * Permintaan outbound dari `Checkout` diarahkan melalui Envoy PEP sidecar menggunakan iptables redirection (`PREROUTING`/`OUTPUT` chains) atau eBPF sockops program.
3. **Decoupled Policy Evaluation**:
   * Envoy PEP membekukan request sementara dan mengirimkan payload `envoy.service.auth.v3.CheckRequest` via gRPC ke OPA PDP.
   * OPA mengurai konteks: Membaca identitas pemanggil dari sertifikat TLS (`spiffe://acme.internal/ns/core/sa/checkout-sa`), memeriksa token JWT dari header, dan memvalidasi device posture via in-memory cached state PIP.
4. **Enforcement & Downstream Handshake**:
   * Jika OPA memutuskan `DENY`, PEP langsung memutus koneksi dan merespons klien dengan HTTP 403 Forbidden tanpa meneruskan paket ke upstream.
   * Jika OPA memutuskan `ALLOW`, PEP melakukan TLS Handshake ke target upstream (`Payment Service`). Sertifikat kedua belah pihak dipertukarkan dan divalidasi silang secara timbal balik (mTLS).
   * Request diproses oleh upstream, dan respons terenkripsi dikembalikan ke pemanggil.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata: Sistem Fasilitas Riset Nuklir Bawah Tanah
* **Perimeter Tradisional**: Seperti pagar gerbang depan komplek riset. Begitu seseorang melewati satpam gerbang depan (misal memakai lencana palsu atau memanjat pagar), orang tersebut bebas berjalan masuk ke reaktor nuklir, ruang server, dan lab biologi karena tidak ada pintu yang terkunci di dalam komplek.
* **Arsitektur Zero Trust**:
  * Komplek riset tidak memiliki "area dalam" yang aman secara inheren.
  * Setiap pintu laboratorium memiliki pemindai biometrik + smart card reader (**PEP**).
  * Kredensial smart card berubah setiap 5 menit via frekuensi radio terenkripsi (**SPIFFE Ephemeral Identity**).
  * Satpam pintu tidak pernah menentukan sendiri apakah Anda boleh masuk. Satpam selalu menelepon sistem komando sentral (**PDP/OPA**) melalui interkom anti-sadap (**gRPC/TLS**).
  * Sistem komando sentral memeriksa jadwal kerja Anda, apakah ada alarm kebakaran aktif di zona tersebut, dan kapan terakhir kali Anda melewati pemeriksaan psikologis (**PIP/Context Engine**).
  * Izin masuk hanya diberikan untuk ruangan tersebut, selama 1 menit, untuk melakukan 1 tugas spesifik (*Least Privilege*).

#### Detail Diagram Arsitektur Kontrol Akses Dinamis

```
 +----------------------------------------------------------------------------------------------------+
 |                                        KUBERNETES WORKER NODE                                      |
 |                                                                                                    |
 |  +-------------------------------------+             +------------------------------------------+  |
 |  | POD: checkout-service               |             | POD: opa-pdp-daemon                      |  |
 |  |                                     |             |                                          |  |
 |  |  +-------------------------------+  |             |  +------------------------------------+  |  |
 |  |  | App Container (Go)            |  |             |  | OPA Runtime Engine                 |  |  |
 |  |  | - Port: 8080                  |  |             |  | - Rego Policy Evaluator            |  |  |
 |  |  +---------------^---------------+  |             |  | - In-Memory Cache (PIP Data)       |  |  |
 |  |                  | (Cleartext)   |  |             |  +-----------------^------------------+  |  |
 |  |                  | Loopback      |  |                                  |                     |  |
 |  |  +---------------v---------------+  |      gRPC ext_authz              |                     |  |
 |  |  | Envoy Proxy (PEP Sidecar)     |==|==================================+                     |  |
 |  |  | - Listens: 0.0.0.0:15001      |  |      /run/ext_authz/socket.sock                        |  |
 |  |  | - SPIFFE SVID Handler         |  |                                                        |  |
 |  |  +---------------^---------------+  |                                                        |  |
 |  +------------------|------------------+                                                        |  |
 |                     |                                                                           |  |
 |                     | UNIX Socket (/run/spire/sockets/agent.sock)                               |  |
 |                     v                                                                           |  |
 |  +-------------------------------------------------------------------------------------------+  |  |
 |  | SPIRE Agent DaemonSet                                                                     |  |  |
 |  | - Workload Attestor (Kernel /proc inspection)                                             |  |  |
 |  | - Key Provisioning (X.509 SVID memory mapping)                                            |  |  |
 |  +-------------------------------------------------------------------------------------------+  |  |
 +----------------------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Validasi Kontekstual Ephemeral Token Berbasis Claims
Contoh sederhana di Go yang mengilustrasikan dynamic evaluation token ephemeral yang memvalidasi `spiffe_id` pemanggil dan postur risiko sebelum memberikan akses ke *critical resource*.

```go
package main

import (
	"context"
	"crypto/subtle"
	"errors"
	"fmt"
	"time"
)

type SecurityContext struct {
	CallerSPIFFEID string
	DeviceTrustScore int // Skala 0 - 100
	IssuedAt         time.Time
	ExpiresAt        time.Time
}

type PolicyEvaluator struct {
	AllowedTrustDomain string
	MinTrustScore      int
}

func (pe *PolicyEvaluator) Evaluate(ctx context.Context, secCtx SecurityContext, requestedAction string) (bool, error) {
	// 1. Verifikasi masa berlaku token (Zero Trust menolak long-lived credentials)
	now := time.Now().UTC()
	if now.After(secCtx.ExpiresAt) || now.Before(secCtx.IssuedAt) {
		return false, errors.New("security context is expired or not yet valid")
	}

	// 2. Evaluasi Trust Domain secara constant-time untuk mitigasi timing attack
	expectedPrefix := fmt.Sprintf("spiffe://%s/", pe.AllowedTrustDomain)
	if len(secCtx.CallerSPIFFEID) < len(expectedPrefix) {
		return false, errors.New("invalid spiffe id format")
	}
	
	prefixMatch := subtle.ConstantTimeCompare(
		[]byte(secCtx.CallerSPIFFEID[:len(expectedPrefix)]),
		[]byte(expectedPrefix),
	)
	if prefixMatch != 1 {
		return false, fmt.Errorf("caller identity %s does not belong to trust domain %s", 
			secCtx.CallerSPIFFEID, pe.AllowedTrustDomain)
	}

	// 3. Evaluasi Postur Keamanan Dinamis (Continuous Context Assessment)
	if secCtx.DeviceTrustScore < pe.MinTrustScore {
		return false, fmt.Errorf("insufficient device trust score: got %d, required >= %d", 
			secCtx.DeviceTrustScore, pe.MinTrustScore)
	}

	// 4. Evaluasi Aksi Khusus
	if requestedAction == "EXECUTE_TRANSACTION" && secCtx.DeviceTrustScore < 85 {
		return false, errors.New("high privilege action requires minimum device score of 85")
	}

	return true, nil
}

func main() {
	evaluator := &PolicyEvaluator{
		AllowedTrustDomain: "fintech.internal",
		MinTrustScore:      70,
	}

	sampleCtx := SecurityContext{
		CallerSPIFFEID:   "spiffe://fintech.internal/ns/prod/sa/payment-service",
		DeviceTrustScore: 88,
		IssuedAt:         time.Now().UTC().Add(-1 * time.Minute),
		ExpiresAt:        time.Now().UTC().Add(5 * time.Minute),
	}

	allowed, err := evaluator.Evaluate(context.Background(), sampleCtx, "EXECUTE_TRANSACTION")
	if err != nil {
		fmt.Printf("Access DENIED: %v\n", err)
		return
	}
	fmt.Printf("Access GRANTED: Result=%t\n", allowed)
}
```

---

#### Practical Example: Enterprise Envoy External Authorization Engine (ext_authz) dengan OPA & SPIFFE Validation

Implementasi server gRPC `ext_authz` kelas produksi dalam Go yang menerima permintaan dari Envoy Proxy, mengekstrak sertifikat SPIFFE mTLS, memeriksa token OIDC, dan memanggil mesin OPA secara in-process SDK.

##### 1. Policy Rule Rego (`authz.rego`)
Simpan di `/policies/authz.rego`. Kebijakan ini menegakkan bahwa:
* Pemanggil harus membawa sertifikat SVID dari trust domain `enterprise.acme`.
* Namespace pemanggil harus `frontend` atau `core`.
* Klien tidak boleh mengakses rute `/admin` tanpa role `security-officer`.

```rego
package enterprise.zero_trust

import future.keywords.in

default allow = false
default reason = "DENY_DEFAULT_CLOSED"

# Ekstraksi atribut input
caller_id := input.attributes.source.certificate
http_request := input.attributes.request.http

# Helper untuk memverifikasi SPIFFE ID prefix
is_valid_trust_domain {
    startswith(caller_id, "spiffe://enterprise.acme/")
}

# Rule Otorisasi L7
allow {
    is_valid_trust_domain
    http_request.method == "GET"
    startswith(http_request.path, "/api/v1/public/")
}

allow {
    is_valid_trust_domain
    caller_id == "spiffe://enterprise.acme/ns/core/sa/checkout-workload"
    http_request.method == "POST"
    http_request.path == "/api/v1/payments/process"
    input.claims.role == "transaction_engine"
    input.claims.device_compliance == true
}

reason = "ALLOW_PERMITTED" {
    allow
}

reason = "DENY_UNAUTHORIZED_CALLER" {
    not is_valid_trust_domain
}

reason = "DENY_PRIVILEGE_MISMATCH" {
    is_valid_trust_domain
    not allow
}
```

##### 2. Production Envoy gRPC ext_authz Server (`main.go`)

```go
package main

import (
	"context"
	"crypto/x509"
	"encoding/pem"
	"fmt"
	"net"
	"net/url"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	corev3 "github.com/envoyproxy/go-control-plane/envoy/config/core/v3"
	authv3 "github.com/envoyproxy/go-control-plane/envoy/service/auth/v3"
	typev3 "github.com/envoyproxy/go-control-plane/envoy/type/v3"
	"github.com/open-policy-agent/opa/rego"
	"google.golang.org/genproto/googleapis/rpc/status"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/reflection"
)

type ZeroTrustAuthServer struct {
	regoQuery rego.PreparedEvalQuery
}

func NewZeroTrustAuthServer(policyFile string) (*ZeroTrustAuthServer, error) {
	policyBytes, err := os.ReadFile(policyFile)
	if err != nil {
		return nil, fmt.Errorf("failed to read policy file: %w", err)
	}

	ctx := context.Background()
	query, err := rego.New(
		rego.Query("result = data.enterprise.zero_trust"),
		rego.Module("authz.rego", string(policyBytes)),
	).PrepareForEval(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to compile rego policy: %w", err)
	}

	return &ZeroTrustAuthServer{regoQuery: query}, nil
}

// ExtractSPIFFEID extracts the SAN URI from a URL-encoded or raw PEM x509 cert
func ExtractSPIFFEID(certRaw string) (string, error) {
	if certRaw == "" {
		return "", errors.New("empty certificate presented")
	}

	unescaped, err := url.QueryUnescape(certRaw)
	if err != nil {
		unescaped = certRaw
	}

	block, _ := pem.Decode([]byte(unescaped))
	if block == nil {
		return "", errors.New("failed to parse certificate PEM block")
	}

	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return "", fmt.Errorf("x509 parse error: %w", err)
	}

	for _, uri := range cert.URIs {
		if strings.HasPrefix(uri.String(), "spiffe://") {
			return uri.String(), nil
		}
	}

	return "", errors.New("no valid SPIFFE SAN found in certificate")
}

func (s *ZeroTrustAuthServer) Check(ctx context.Context, req *authv3.CheckRequest) (*authv3.CheckResponse, error) {
	start := time.Now()

	// Ekstraksi Client Certificate dari Envoy Attributes
	var clientCert string
	if req.Attributes != nil && req.Attributes.Source != nil {
		clientCert = req.Attributes.Source.Certificate
	}

	spiffeID, err := ExtractSPIFFEID(clientCert)
	if err != nil {
		// Fallback for demonstration if Envoy passes SPIFFE ID via x-forwarded-client-cert header
		if req.Attributes != nil && req.Attributes.Request != nil && req.Attributes.Request.Http != nil {
			spiffeID = req.Attributes.Request.Http.Headers["x-authenticated-spiffe-id"]
		}
	}

	// Buat payload input untuk evaluasi Rego
	inputPayload := map[string]interface{}{
		"attributes": map[string]interface{}{
			"source": map[string]interface{}{
				"certificate": spiffeID,
			},
			"request": map[string]interface{}{
				"http": map[string]interface{}{
					"method": req.Attributes.Request.Http.Method,
					"path":   req.Attributes.Request.Http.Path,
					"host":   req.Attributes.Request.Http.Host,
				},
			},
		},
		"claims": map[string]interface{}{
			// Pada produksi nyata, claims ini didekode dari Verified JWT Payload via PIP
			"role":              "transaction_engine",
			"device_compliance": true,
		},
	}

	results, err := s.regoQuery.Eval(ctx, rego.EvalInput(inputPayload))
	duration := time.Since(start)

	if err != nil {
		fmt.Printf("[PDP ERROR] Evaluation error: %v, took %dus\n", err, duration.Microseconds())
		return &authv3.CheckResponse{
			Status: &status.Status{
				Code:    int32(codes.Internal),
				Message: "Internal authorization engine error",
			},
		}, nil
	}

	if len(results) > 0 {
		bindings := results[0].Bindings["result"].(map[string]interface{})
		isAllowed, _ := bindings["allow"].(bool)
		reason, _ := bindings["reason"].(string)

		if isAllowed {
			fmt.Printf("[PDP ALLOW] Caller: %s, Path: %s, Reason: %s, Latency: %dus\n", 
				spiffeID, req.Attributes.Request.Http.Path, reason, duration.Microseconds())
			
			return &authv3.CheckResponse{
				Status: &status.Status{Code: int32(codes.OK)},
				HttpResponse: &authv3.CheckResponse_OkResponse{
					OkResponse: &authv3.OkHttpResponse{
						Headers: []*corev3.HeaderValueOption{
							{
								Header: &corev3.HeaderValue{
									Key:   "x-auth-verified-spiffe",
									Value: spiffeID,
								},
							},
							{
								Header: &corev3.HeaderValue{
									Key:   "x-auth-decision-latency-us",
									Value: fmt.Sprintf("%d", duration.Microseconds()),
								},
							},
						},
					},
				},
			}, nil
		}

		fmt.Printf("[PDP DENY] Caller: %s, Path: %s, Reason: %s, Latency: %dus\n", 
			spiffeID, req.Attributes.Request.Http.Path, reason, duration.Microseconds())
	}

	return &authv3.CheckResponse{
		Status: &status.Status{
			Code:    int32(codes.PermissionDenied),
			Message: "Zero Trust Policy Rejection: Access not explicitly permitted",
		},
		HttpResponse: &authv3.CheckResponse_DeniedResponse{
			DeniedResponse: &authv3.DeniedHttpResponse{
				Status: &typev3.HttpStatus{
					Code: typev3.StatusCode_Forbidden,
				},
				Body: `{"error":"AccessDenied","message":"Zero Trust policy validation failed"}`,
				Headers: []*corev3.HeaderValueOption{
					{
						Header: &corev3.HeaderValue{
							Key:   "Content-Type",
							Value: "application/json",
						},
					},
				},
			},
		},
	}, nil
}

func main() {
	port := 9001
	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		panic(fmt.Sprintf("Failed to listen on port %d: %v", port, err))
	}

	server, err := NewZeroTrustAuthServer("authz.rego")
	if err != nil {
		panic(fmt.Sprintf("Failed to initialize ZT Auth Engine: %v", err))
	}

	grpcServer := grpc.NewServer(
		grpc.MaxConcurrentStreams(10000),
		grpc.ConnectionTimeout(2*time.Second),
	)

	authv3.RegisterAuthorizationServer(grpcServer, server)
	reflection.Register(grpcServer)

	go func() {
		fmt.Printf("Zero Trust ext_authz PDP server listening on :%d\n", port)
		if err := grpcServer.Serve(lis); err != nil {
			fmt.Printf("PDP Server terminated: %v\n", err)
		}
	}()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	fmt.Println("Gracefully stopping PDP server...")
	grpcServer.GracefulStop()
}
```

---

### 8. Real World Case Study: Arsitektur Transaksi FinTech Tier-1

#### Konteks & Masalah
Sebuah institusi sistem pembayaran memproses 35.000 Transaksi Per Detik (TPS). Sistem awal mengandalkan arsitektur *network perimeter* konvensional (Core Banking di dalam Private Subnet, dilindungi Next-Gen Firewall). 
* **Insiden**: Penyerang mengompromikan satu pod *Report Generator* yang memiliki library third-party rentan (CVE Remote Code Execution). Menggunakan pod tersebut, penyerang memindai port database internal PostgreSQL dan berhasil melakukan *credential dumping* karena subnet database mempercayai semua lalu lintas dari subnet aplikasi.
* **Tantangan Rekayasa**: Manajemen mewajibkan implementasi NIST SP 800-207 Zero Trust penuh dalam 6 bulan dengan kriteria:
  * Overhead latensi absolut per lompatan RPC: $\le 1.8 \text{ ms}$ pada p99.
  * *Zero downtimes* selama migrasi 120+ microservices.
  * Audit compliance memenuhi standar PCI-DSS 4.0 Bab Otorisasi Spesifik & mTLS.

#### Desain Solusi Arsitektural
1. **Penerbitan Identitas Kriptografis Workload (SPIRE Integration)**:
   * Setiap Kubernetes cluster dioperasikan dengan satu SPIRE Agent per worker node.
   * Workload didefinisikan menggunakan format SPIFFE ID:
     `spiffe://bank.internal/env/{env}/ns/{namespace}/sa/{serviceaccount}`.
   * Sertifikat X.509 SVID dirotasi otomatis setiap 60 menit. Durasi pendek ini membatasi jendela waktu pemanfaatan sertifikat jika terjadi kebocoran memori.
2. **Sidecar Data Plane & Dynamic In-Memory Evaluation**:
   * Menghindari network hop eksternal saat PDP dihubungi, OPA dikompilasi ke WebAssembly (Wasm) atau diintegrasikan sebagai shared-memory sidecar daemon pada loopback (`127.0.0.1:9001`) di setiap pod.
   * PEP (Envoy) mengecek aturan OPA via socket IPC lokal. Overhead handshake dan evaluasi ditekan menjadi rata-rata 320 mikrodetik.
3. **Pemberlakuan Default-Deny Microsegmentation Layer 4/Layer 7**:
   * Penegakan aturan L4 diberlakukan menggunakan Cilium eBPF host routing: Matriks komunikasi dibatasi sehingga pod *Report Generator* secara kernel-level dijatuhkan (*packet dropped*) jika mencoba membuka socket TCP ke port PostgreSQL core banking.
   * Penegakan aturan L7 memeriksa validitas klaim finansial (misal: hanya pod `payment-orchestrator` yang membawa token transaksi tertanda HSM yang dapat memanggil rute `/v1/ledger/debit`).

#### Hasil Pengukuran Produksi
* **Blast Radius Reduction**: Penetrasi internal simulasi (Red Teaming) pasca-implementasi menunjukkan bahwa pengompromian pod report generator terisolasi secara total; penyerang tidak dapat mendeteksi, melakukan ping, maupun membaca port database ledger.
* **Performa SLA**:
  * Baseline Latency (Non-ZTA Cleartext): p99 = $14.2 \text{ ms}$
  * ZTA Latency (mTLS 1.3 + OPA PDP via socket): p99 = $15.7 \text{ ms}$
  * Total kenaikan latensi p99: $+1.5 \text{ ms}$ (Sesuai target SLA $< 1.8 \text{ ms}$).

---

### 9. Trade-offs: Analisis Multi-Dimensi

Penerapan Zero Trust bukan keputusan tanpa konsekuensi. Tabel berikut merinci konsekuensi teknis arsitektural yang harus diantisipasi oleh Software Architect:

```
+---------------------------------------------------------------------------------------------------------+
|                                    TRADE-OFF MATRIX ZERO TRUST                                          |
+----------------------+------------------------------------+---------------------------------------------+
| Dimensi Teknis       | Pilihan Konfigurasi                | Konsekuensi Negatif / Trade-Off             |
+----------------------+------------------------------------+---------------------------------------------+
| Postur Eksekusi PDP  | Fail-Closed (Default Deny)         | False positive pemadaman servis massal saat |
|                      |                                    | OPA PDP mengalami degradasi CPU/OOM.        |
|                      | Fail-Open                          | Pembobolan keamanan; bypass otorisasi saat   |
|                      |                                    | PDP mengalami crash.                        |
+----------------------+------------------------------------+---------------------------------------------+
| Umur SVID SPIFFE     | Singkat (e.g., 15 - 30 Menit)      | Memaksimalkan keamanan; namun melipatganda- |
|                      |                                    | kan I/O beban CPU pada SPIRE Server/Agent   |
|                      |                                    | dan risiko *certificate renewal storm*.     |
|                      | Panjang (e.g., 24 - 72 Jam)        | Risiko *replay attack* dan kesulitan revokasi|
|                      |                                    | sertifikat aktif sebelum masa expired usai. |
+----------------------+------------------------------------+---------------------------------------------+
| Deployment PDP       | Centralized Cluster PDP            | Manajemen terpusat; namun menambah latency  |
|                      |                                    | network hop (+2-5ms) & PDP jadi Single Point|
|                      |                                    | of Failure (SPOF).                          |
|                      | Sidecar / Local Socket Node        | Latensi ultra rendah (<0.5ms); namun konsumsi|
|                      |                                    | total RAM node melonjak drastis (memory tax)|
+----------------------+------------------------------------+---------------------------------------------+
| Data Plane Isolation | eBPF + Sidecar Mesh (L4+L7)        | Isolasi komprehensif; namun debugging paket |
|                      |                                    | sangat rumit, tracing network butuh tooling |
|                      |                                    | kernel canggih, dan overhead CPU per pod.   |
+----------------------+------------------------------------+---------------------------------------------+
```

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Antipatterns):
1. **Mengabaikan "Fail-Closed" Avalanche**: Ketika PDP sentral mengalami overload, seluruh PEP serentak menolak permintaan klien. Ketiadaan *circuit breaker* atau *graceful fallback policy cache* dapat melumpuhkan seluruh platform secara total (*cascading outage*).
2. **Sertifikat X.509 Tanpa Revocation Strategy**: Mengasumsikan bahwa mTLS otomatis aman tanpa mendesain arsitektur rotasi. Jika *private key* dari sebuah microservice bocor dan umur sertifikat diset 30 hari tanpa mekanisme *CRL/OCSP* atau rotasi ultra-cepat SPIRE, penyerang memiliki akses persisten tanpa batas waktu.
3. **Overhead Parsing Kriptografis Berulang (Regex & Token Decoding)**: Menjalankan parsing JWT dan kripto verifikasi tanda tangan secara berulang di setiap layer internal (misal di API Gateway, Service Mesh Ingress, dan aplikasi downstream) tanpa memanfaatkan *header passing identity injection* yang sudah terotentikasi.
4. **IP-in-Rego Logic**: Menuliskan aturan otorisasi berbasis CIDR atau hardcoded subnet IP di dalam PDP Rego. Tindakan ini merusak esensi ZTA yang berbasis identitas kriptografis dan memicu *maintenance nightmare* ketika terjadi restrukturisasi subnet cloud.

#### Panduan Troubleshooting Lapangan:
* **Kasus 1: Envoy Mengembalikan HTTP 503 dengan Error `UC` atau `UF`**:
  * *Penyebab*: `UF` (*Upstream Connection Failure*) atau `UC` (*Upstream Connection Termination*) sering terjadi akibat kegagalan handshake mTLS. Upstream menolak sertifikat klien yang disajikan oleh Envoy PEP.
  * *Diagnosa*:
    ```bash
    # Periksa log Envoy pada level debug
    kubectl logs checkout-pod -c envoy --tail=100 | grep -E "ssl|handshake|ext_authz"
    # Uji validitas sertifikat SPIRE yang aktif di dalam pod
    openssl s_client -connect payment-service:8443 \
      -cert /run/secrets/spiffe/tls.crt \
      -key /run/secrets/spiffe/tls.key \
      -CAfile /run/secrets/spiffe/ca.crt
    ```
* **Kasus 2: Latensi Meningkat Misterius pada Jam Sibuk (p99 > 100ms)**:
  * *Penyebab*: PDP OPA kehabisan thread worker atau terjadi *lock contention* saat mengevaluasi dokumen data JSON berukuran besar di memory.
  * *Diagnosa*:
    ```bash
    # Periksa waktu evaluasi OPA via metrik internal Prometheus
    curl -s http://localhost:9001/v1/metrics | grep "go_memstats_gc_pause_ns"
    curl -s http://localhost:9001/v1/metrics | grep "opa_rego_evaluation_duration_seconds"
    # Pastikan data PIP yang di-query bersifat pre-indexed menggunakan object lookup bukan array scanning (O(1) vs O(N))
    ```
* **Kasus 3: Workload Gagal Mengambil SVID dari SPIRE Agent Socket**:
  * *Penyebab*: Kesalahan mount Unix Domain Socket permission atau node attestor gagal memvalidasi identitas pod akibat namespace labeling yang salah.
  * *Diagnosa*:
    ```bash
    # Periksa health SPIRE agent pada worker node target
    spire-agent healthcheck -socketPath /run/spire/sockets/agent.sock
    # Jalankan profiling attestation
    spire-agent api fetch -socketPath /run/spire/sockets/agent.sock
    ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis arsitektur Zero Trust ke *Production*:

- [ ] **Decoupled Architecture**: PEP dan PDP terpisah secara modular; tidak ada evaluasi logic bisnis manual yang di-hardcode di dalam controller kode microservice.
- [ ] **SPIRE Workload Attestation Rigor**: Menggunakan kombinasi minimal 2 selektor beban kerja independen (contoh: `k8s:ns` DAN `k8s:sa` DAN `k8s:pod-uid`).
- [ ] **Ephemeral Lifetimes**: Durasi hidup SVID X.509 diatur maksimal 60 menit dengan *auto-renewal* saat masa aktif tersisa 50%.
- [ ] **Fail-Safe Mechanism**: Konfigurasi PDP mendefinisikan timeout yang ketat ($\le 50 \text{ ms}$) dan fallback terisolasi yang terprediksi jika PDP tidak merespons.
- [ ] **mTLS Strict Enforcement**: Port servis aplikasi target (`upstream`) hanya mendengarkan pada interface localhost loopback atau diisolasi menggunakan NetworkSecurityPolicy sehingga *cleartext bypassing* tidak dapat dilakukan.
- [ ] **Cryptographic In-Memory Handling**: Tidak ada *private key* yang ditulis ke disk/SSD; seluruh penanganan kunci kripto dilakukan via Unix Domain Socket memori virtual atau tmpfs.
- [ ] **Audit Trail Tamper-Proofing**: Setiap keputusan otorisasi PDP (baik ALLOW maupun DENY) dicatat dalam format terstruktur (JSON/NDJSON) dan dikirim ke append-only log cluster (SIEM) yang terenkripsi.
- [ ] **Static Rego Verification**: Seluruh file `.rego` diuji unit-nya secara otomatis menggunakan `opa test` di dalam pipeline CI/CD sebelum deployment ke lingkungan produksi.

---

### 12. Hands-on Practice: Membangun PEP, PDP & Dynamic Authorizer Terisolasi

Simpan seluruh file praktikum ini di direktori: `hands-on/m02/`

#### Struktur Proyek:
```
hands-on/m02/
├── Makefile
├── envoy.yaml
├── policies/
│   ├── authz.rego
│   └── authz_test.rego
└── main.go (ext_authz PDP Engine)
```

#### Langkah 1: Tulis Unit Test Rego (`policies/authz_test.rego`)
```rego
package enterprise.zero_trust

test_allow_valid_checkout_caller {
    allow with input as {
        "attributes": {
            "source": {"certificate": "spiffe://enterprise.acme/ns/core/sa/checkout-workload"},
            "request": {"http": {"method": "POST", "path": "/api/v1/payments/process"}}
        },
        "claims": {"role": "transaction_engine", "device_compliance": true}
    }
}

test_deny_untrusted_domain {
    not allow with input as {
        "attributes": {
            "source": {"certificate": "spiffe://attacker.domain/ns/core/sa/rogue-workload"},
            "request": {"http": {"method": "POST", "path": "/api/v1/payments/process"}}
        },
        "claims": {"role": "transaction_engine", "device_compliance": true}
    }
}

test_deny_unauthorized_route {
    not allow with input as {
        "attributes": {
            "source": {"certificate": "spiffe://enterprise.acme/ns/core/sa/checkout-workload"},
            "request": {"http": {"method": "DELETE", "path": "/api/v1/payments/delete"}}
        },
        "claims": {"role": "transaction_engine", "device_compliance": true}
    }
}
```

#### Langkah 2: Buat Konfigurasi Envoy PEP (`envoy.yaml`)
```yaml
static_resources:
  listeners:
  - name: ingress_listener
    address:
      socket_address:
        address: 0.0.0.0
        port_value: 10000
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress_http
          route_config:
            name: local_route
            virtual_hosts:
            - name: local_service
              domains: ["*"]
              routes:
              - match:
                  prefix: "/"
                route:
                  cluster: target_upstream_service
          http_filters:
          - name: envoy.filters.http.ext_authz
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.ext_authz.v3.ExtAuthz
              grpc_service:
                envoy_grpc:
                  cluster_name: ext_authz_pdp_service
                timeout: 0.25s
              transport_api_version: V3
              with_request_body:
                max_request_bytes: 1024
                pack_as_bytes: false
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router

  clusters:
  - name: target_upstream_service
    connect_timeout: 0.25s
    type: LOGICAL_DNS
    dns_lookup_family: V4_ONLY
    lb_policy: ROUND_ROBIN
    load_assignment:
      cluster_name: target_upstream_service
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: httpbin.org
                port_value: 80

  - name: ext_authz_pdp_service
    connect_timeout: 0.25s
    type: STATIC
    lb_policy: ROUND_ROBIN
    http2_protocol_options: {}
    load_assignment:
      cluster_name: ext_authz_pdp_service
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: 127.0.0.1
                port_value: 9001
```

#### Langkah 3: Eksekusi Otomasi (`Makefile`)
```makefile
.PHONY: test-policy run-pdp run-envoy simulate-attack simulate-legit

test-policy:
	opa test policies/ -v

run-pdp:
	go run main.go

run-envoy:
	envoy -c envoy.yaml

simulate-attack:
	@echo ">> Testing Untrusted Caller (Expected: 403 Forbidden)..."
	curl -i -X POST http://localhost:10000/api/v1/payments/process \
		-H "x-authenticated-spiffe-id: spiffe://attacker.domain/sa/bad"

simulate-legit:
	@echo ">> Testing Legitimate Workload (Expected: Upstream 200/404 OK response)..."
	curl -i -X POST http://localhost:10000/api/v1/payments/process \
		-H "x-authenticated-spiffe-id: spiffe://enterprise.acme/ns/core/sa/checkout-workload"
```

---

### 13. Exercise

#### Level: Easy
1. Modifikasi file `policies/authz.rego` agar menambahkan verifikasi waktu: Request hanya diizinkan (`allow`) jika atribut `input.attributes.request.time` berada pada jam kerja operasional kantor (antara jam 08:00 sampai 18:00 UTC).
2. Tuliskan 1 unit test Rego di `policies/authz_test.rego` untuk membuktikan bahwa request di luar jam kerja tersebut menghasilkan status `DENY`.

#### Level: Medium
1. Implementasikan mekanisme *Cache Invalidation Policy* pada server PDP Go `main.go`. PDP harus menyediakan endpoint admin HTTP terpisah (`/admin/reload-policy`) yang secara dinamis mengompilasi ulang dokumen Rego dari disk ke memory tanpa me-restart server gRPC yang sedang menangani live traffic.

#### Level: Hard
1. Buat custom PIP Provider di dalam Go PDP yang melakukan query asinkronus ke server mock Redis (latensi buatan 1ms) untuk memvalidasi apakah SPIFFE ID klien berada di dalam status pemblokiran aktif (*revocation/blacklisting list*).
2. Terapkan algoritma *local LRU caching* untuk hasil query PIP tersebut dengan TTL 5 detik untuk menjaga throughput PDP tetap berada di atas 10.000 QPS tanpa mengalami *network socket exhaustion* ke Redis.

---

### 14. Challenge

**Studi Kasus**: Anda ditugaskan sebagai Chief Security Architect untuk platform e-Commerce Unicorn yang menghadapi insiden: Seorang penyerang berhasil mencuri token Service Account Kubernetes level namespace dari cluster staging dan mencoba memakainya untuk menguras saldo poin reward via cluster produksi melalui VPC Interconnect.

**Instruksi Rekayasa**:
1. Rancang secara komprehensif diagram arsitektur pertahanan *Dual-Trust Perimeter* yang memisahkan ekosistem Staging dan Production secara absolut mengacu pada NIST SP 800-207.
2. Definisikan bagaimana federasi SPIFFE (`SPIFFE Trust Domain Federation`) dikonfigurasi agar trust-domain `spiffe://staging.acme` **mustahil** mendapatkan verifikasi validitas dari trust-domain `spiffe://prod.acme`, meskipun kunci signing Root CA mereka di-issue oleh entitas penyedia Cloud KMS yang sama.
3. Desain kebijakan fallback pada PEP Envoy: Jika PDP lokal crash atau mati akibat Out Of Memory (OOM), rancang mitigasi di mana hanya lalu lintas *Read-Only* tersertifikasi tertentu yang dapat lewat sementara (degraded mode), sedangkan seluruh mutasi saldo finansial dibekukan secara total (*fail-closed*), lengkap dengan formulasi metrik alerting deteksinya.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual)
1. **Komponen NIST SP 800-207 yang bertindak sebagai pintu gerbang langsung pemutus koneksi data plane adalah:**
   * A. Policy Decision Point (PDP)
   * B. Policy Enforcement Point (PEP)
   * C. Policy Information Point (PIP)
   * D. Policy Administration Point (PAP)
   * *Jawaban*: **B**. PEP adalah entitas data plane yang mencegat dan mengontrol arus paket jaringan.

2. **Apa yang mendasari pemikiran penghapusan alamat IP sebagai identitas primer pada arsitektur Zero Trust?**
   * A. Alamat IP membutuhkan memori RAM terlalu besar untuk diproses Envoy.
   * B. Protokol TCP/IP tidak mendukung enkripsi data payload.
   * C. Alamat IP bersifat dinamis, rentan spoofing, dan tidak merepresentasikan identitas beban kerja secara kriptografis.
   * D. Alamat IP tidak kompatibel dengan spesifikasi REST API.
   * *Jawaban*: **C**. Di era kontainerisasi dan multi-tenant cloud, IP bersifat ephemeral dan mudah dimanipulasi.

3. **Format URI representasi identitas standar pada spesifikasi SPIFFE adalah:**
   * A. `urn:oidc:trustdomain:workload:id`
   * B. `spiffe://<trust-domain>/<workload-path>`
   * C. `https://<trust-domain>/identity/x509`
   * D. `x509://<trust-domain>/serial/<hash>`
   * *Jawaban*: **B**. Spesifikasi SPIFFE menetapkan skema URL seragam `spiffe://<trust-domain>/<path>`.

4. **Karakteristik utama sertifikat X.509 SVID yang diterbitkan oleh SPIRE untuk memitigasi blast radius pencurian kunci adalah:**
   * A. Masa berlaku sangat panjang (1-2 tahun) tanpa private key.
   * B. Bersifat ephemeral (durasi hitungan menit/jam) dan dirotasi secara in-memory.
   * C. Memerlukan intervensi manual sistem administrator untuk merotasi file.
   * D. Ditanam secara statis ke dalam Docker container image saat fase build.
   * *Jawaban*: **B**. Durasi hidup singkat membatasi waktu eksploitasi jika sertifikat disusupi.

5. **Apa fungsi dari PAP (Policy Administration Point)?**
   * A. Menginterogasi kernel Linux untuk mendeteksi ID proses container.
   * B. Menerbitkan sertifikat mTLS ke pod aplikasi.
   * C. Tempat di mana kebijakan otorisasi ditulis, dikelola, dan diverifikasi sebelum didistribusikan.
   * D. Mencegat paket HTTP/2 untuk dievaluasi kuerinya.
   * *Jawaban*: **C**. PAP adalah domain manajemen aturan (misalnya Git Repository / Management Plane).

---

#### Bagian 2: Intermediate (Pilihan Ganda / Pemecahan Masalah)
6. **Dalam integrasi Envoy Proxy dan OPA melalui protokol gRPC ext_authz, apa yang terjadi jika konfigurasi diset `failure_mode_allow: false` dan service OPA mati mendadak?**
   * A. Envoy meneruskan seluruh paket request ke upstream tanpa verifikasi.
   * B. Envoy menolak seluruh request yang masuk dan mengembalikan HTTP status 503 / 403 (*Fail-Closed*).
   * C. Envoy otomatis mematikan dirinya sendiri untuk melindungi host.
   * D. Envoy mencoba menghubungi database aplikasi secara langsung.
   * *Jawaban*: **B**. `failure_mode_allow: false` menegakkan postur *fail-closed*, mematikan akses demi menjaga postur keamanan saat PDP offline.

7. **Mengapa evaluasi kebijakan berbasis Rego/OPA dianjurkan dieksekusi secara in-process SDK atau IPC local-socket ketimbang memanggil remote HTTP API terpusat?**
   * A. Karena OPA tidak mendukung protokol jaringan HTTP.
   * B. Untuk menghindari tambahan latensi network hop dan risiko kegagalan koneksi terdistribusi pada critical path otorisasi.
   * C. Karena bahasa Rego tidak bisa di-compile ke dalam format biner.
   * D. Untuk mencegah penggunaan CPU pada worker node lokal.
   * *Jawaban*: **B**. Remote hop menambah 2-10ms overhead per RPC; local socket menekan latensi menjadi sub-milidetik.

8. **Proses di mana SPIRE Agent mengidentifikasi informasi pod lokal melalui penelusuran status kernel Linux (`/proc/<pid>/cgroup`) dikenal sebagai:**
   * A. Node Attestation
   * B. Workload Attestation
   * C. Dynamic Secret Generation
   * D. Token Exchange Protocol
   * *Jawaban*: **B**. Workload Attestation adalah proses memvalidasi atribut proses lokal kontainer melalui kernel host.

9. **Manakah dari skenario berikut yang melanggar prinsip *Continuous Verification* dalam Zero Trust?**
   * A. Memeriksa validitas mTLS dan token JWT pada setiap kali request L7 dieksekusi.
   * B. Memberikan sesi login valid selama 24 jam tanpa re-evaluasi postur keamanan jika perangkat pengguna mendadak terinfeksi malware.
   * C. Melakukan rotasi ephemeral key secara otomatis setiap 30 menit.
   * D. Mengisolasi beban kerja secara kernel level menggunakan eBPF.
   * *Jawaban*: **B**. Asumsi bahwa satu kali lolos autentikasi awal memberikan kepercayaan permanen adalah pelanggaran fatal prinsip Continuous Verification.

10. **Apa keunggulan menggunakan microsegmentation L4 berbasis eBPF dibandingkan iptables tradisional pada cluster berskala ribuan pod?**
    * A. eBPF tidak membutuhkan kernel Linux untuk bekerja.
    * B. eBPF mengeksekusi routing logic dengan kompleksitas $O(1)$ via hash map kernel, sementara iptables mengalami degradasi performa $O(N)$ seiring bertambahnya jumlah rules.
    * C. iptables tidak mendukung protokol TCP.
    * D. eBPF dapat bekerja tanpa hak akses root saat proses inisialisasi.
    * *Jawaban*: **B**. Pada skala masif ribuan pod, evaluasi sekuensial iptables memicu lonjakan beban CPU dan latensi jaringan, sementara eBPF menggunakan BPF maps berkecepatan tinggi.

---

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus A**:
    Platform e-Commerce Anda mengalami *traffic spike* Flash Sale 10x lipat. Metrik menunjukkan latensi pembayaran melonjak dari 20ms menjadi 1.200ms. Setelah diinvestigasi, Envoy PEP menghabiskan 80% waktu tunggu pada pemanggilan OPA PDP via socket. CPU OPA PDP mencapai 100%. Log OPA menunjukkan evaluasi aturan Rego memindai array JSON berukuran 5MB yang memuat daftar seluruh pengguna terblokir (`blacklist: [...]`).
    *Pertanyaan*: Apa kesalahan desain arsitektur yang terjadi, dan bagaimana solusinya secara terstruktur?
    * *Jawaban Solusi*: Kesalahan: Melakukan scanning sekuensial array $O(N)$ di dalam rule engine OPA untuk setiap request masuk. Solusi: Ubah struktur data blacklist menjadi Hash Set/Key-Value object lookup $O(1)$ di memory (`blacklist: {"user_id": true}`). Pindahkan data blacklist berukuran besar ke Redis lokal atau in-memory OPA context cache terindeks, dan pastikan OPA diprofiling menggunakan CPU profiler bawaan untuk mendeteksi *rule evaluation bottlenecks*.

12. **Skenario Kasus B**:
    Sebuah microservice analitik baru di-deploy ke cluster produksi. Namun microservice ini terus mendapatkan respons `HTTP 403 Forbidden` saat mencoba memanggil Microservice Core Data. Log Envoy PEP pada Core Data mencatat error: `ext_authz denied: DENY_UNAUTHORIZED_CALLER`. SPIRE server log menunjukkan status normal.
    *Pertanyaan*: Sebutkan 3 langkah investigasi forensik untuk mengisolasi akar masalah ini!
    * *Jawaban Solusi*:
      1. Ekstraksi sertifikat x509 yang dibawa oleh microservice analitik; verifikasi apakah isi SAN URI sesuai format SPIFFE ID yang diizinkan dalam Rego policy (`authz.rego`).
      2. Periksa ServiceAccount dan Namespace deployment Analitik di Kubernetes; apakah cocok dengan Workload Registration Entry yang didaftarkan di SPIRE Server (apakah ada typo pada selector `k8s:sa` atau `k8s:ns`).
      3. Periksa aturan OPA Rego di sisi Core Data: Pastikan klaim rute HTTP (`method` dan `path`) mencakup izin akses endpoint yang diminta oleh servis analitik tersebut.

13. **Skenario Kasus C**:
    Tim operasional infrastruktur Anda ingin mengaktifkan mTLS di seluruh cluster. Namun, ada 5 aplikasi legacy monolitik yang berjalan di VM bare-metal tua dengan runtime lama yang tidak mendukung TLS 1.3 dan tidak memiliki kemampuan memanggil SPIFFE Workload API.
    *Pertanyaan*: Bagaimana Anda mendesain arsitektur transisi Zero Trust untuk mengakomodasi aplikasi legacy ini tanpa menurunkan standar keamanan microservice modern lainnya?
    * *Jawaban Solusi*: Menerapkan pola **Identity-Aware Proxy (Egress/Ingress Sidecar Gateway)** di host VM legacy: Pasang Envoy Proxy lokal di depan aplikasi legacy pada VM tersebut. Envoy bertindak sebagai PEP lokal yang bertugas mengambil SVID dari SPIRE Agent lokal, menegosiasikan enkripsi mTLS 1.3 modern ke cluster luar, dan meneruskan paket ke aplikasi legacy via loopback lokal (`127.0.0.1`) secara terisolasi. Dengan pola ini, aplikasi legacy tetap terenkapsulasi di dalam batas Zero Trust tanpa perlu mengubah kode sumber aplikasi sama sekali.

---

### 16. Summary

1. **Zero Trust Architecture (ZTA)** menghilangkan konsep kepercayaan implisit (*implicit trust*) berbasis lokasi fisik atau segmen jaringan (IP Address/Subnet) dan menggantinya dengan verifikasi terus menerus (*Continuous Verification*) berbasis identitas kriptografis dan evaluasi konteks dinamis.
2. Mengacu pada kerangka kerja **NIST SP 800-207**, arsitektur sistem memisahkan **Control Plane** (PDP, PIP, PAP) yang mengomputasi izin akses, dari **Data Plane** (PEP) yang mencegat dan menegakkan keputusan akses pada level paket L4/L7.
3. Standar **SPIFFE/SPIRE** memecahkan masalah identitas beban kerja (*workload identity*) terdistribusi dengan menyediakan sertifikat X.509 SVID yang bersifat ephemeral, dirotasi otomatis secara in-memory, dan diotentikasi langsung ke kernel host Linux via proses *Workload Attestation*.
4. Kombinasi **Envoy Proxy (PEP)** dan **Open Policy Agent (PDP)** melalui protokol gRPC `ext_authz` menyediakan infrastruktur otorisasi performa tinggi dengan latensi sub-milidetik, memungkinkan penegakan kebijakan deklaratif (Rego) secara seragam di seluruh organisasi.
5. Rekayasa Zero Trust enterprise menuntut keseimbangan trade-off multidimensi: Menegakkan keamanan absolut (*fail-closed*) harus diimbangi dengan strategi ketahanan tinggi (*high-availability PDP*, in-memory caching, dan eBPF microsegmentation) agar tidak memicu kegagalan sistem yang meluas (*cascading failure*).