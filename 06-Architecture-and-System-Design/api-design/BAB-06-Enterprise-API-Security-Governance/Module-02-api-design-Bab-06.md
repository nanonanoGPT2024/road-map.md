# Kurikulum Enterprise: API Design & Architecture
## Kategori: 06-Architecture-and-System-Design
### BAB-06: Enterprise API Security & Governance
#### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Mendesain dan mengimplementasikan** arsitektur keamanan API berbasis *Zero-Trust*, memadukan *Mutual TLS (mTLS)* di level *service mesh* dengan validasi otorisasi berbasis konteks dinamis (*Attribute-Based Access Control* / ABAC).
- **Mengonstruksi** *Policy Decision Point* (PDP) dan *Policy Enforcement Point* (PEP) terdesentralisasi menggunakan *Open Policy Agent* (OPA) dan *Envoy Proxy* untuk menegakkan *Policy-as-Code*.
- **Menerapkan** mitigasi komprehensif terhadap kerentanan OWASP API Security Top 10 (khususnya BOLA, BFLA, dan *Broken Object Property Level Authorization*) menggunakan pola validasi kriptografi dan *Token Exchange* (RFC 8693).
- **Membangun** sistem tata kelola API (*API Governance*) otomatis dalam *pipeline* CI/CD, mencakup *contract linting*, deteksi *breaking change*, dan penegakan skema audit PII (*Personally Identifiable Information*).
- **Mengoptimalkan** performa subsistem otorisasi terdistribusi dengan target latensi overhead $p99 < 3\text{ ms}$ pada beban traffic $\ge 25.000\text{ RPS}$.

---

### 2. Prerequisite
Peserta wajib menguasai:
- Protokol dasar HTTP/2, HTTP/3, TLS 1.3 handshake, dan kriptografi asimetris (PKI, X.509, RSA, ECDSA).
- Konsep dasar autentikasi web: OAuth 2.0 framework, OpenID Connect (OIDC), dan struktur JSON Web Token (JWT / RFC 7519).
- Pemrograman Go (Golang) tingkat menengah (concurrency primitives, pointer semantics, network/HTTP middleware).
- Dasar orkestrasi kontainer (Kubernetes networking, Ingress controllers, sidecar pattern) dan distributed storage (Redis data structures).

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur keamanan API enterprise modern mengabaikan paradigma *perimeter-based security* ("hard shell, soft interior") dan mengadopsi model **Zero-Trust Network Architecture (ZTNA)**. Di level produksi, arsitektur ini memisahkan secara tegas antara transmisi identitas, evaluasi kebijakan (*Policy Evaluation*), dan eksekusi logika domain (*Business Execution*).

```
[ Edge Client ]
       │ TLS 1.3 (Public CA)
       ▼
┌────────────────────────────────────────────────────────┐
│ API Gateway / WAF Tier (PEP - Perimeter)               │
│ - Rate Limiting (Redis Cluster Sliding Window)        │
│ - TLS Termination & Client Cert Forwarding             │
│ - JWT Verification (JWKS Cache)                        │
└───────────────────────┬────────────────────────────────┘
                        │ mTLS (Internal SPIFFE/SPIRE CA)
                        ▼
┌────────────────────────────────────────────────────────┐
│ Service Mesh Envoy Proxy (PEP - Microsegmentation)     │
│ ┌──────────────────────┴─────────────────────────────┐ │
│ │ Service Pod                                        │ │
│ │  ┌───────────────┐           ┌──────────────────┐  │ │
│ │  │ Go App Service│◄──IPC─────┤ OPA Engine       │  │ │
│ │  │ (Domain Logic)│           │ (PDP - Local Rego│  │ │
│ │  └───────┬───────┘           │  In-Memory Sync) │  │ │
│ │          │                   └─────────▲────────┘  │ │
│ └──────────┼─────────────────────────────┼───────────┘ │
└────────────┼─────────────────────────────┼─────────────┘
             │ Audit Event (Asynchronous)  │ Bundle Sync
             ▼                             ▼
┌─────────────────────────┐   ┌──────────────────────────┐
│ Kafka Tamper-Proof Audit│   │ OPA Control Plane        │
│ Log (WORM Storage)      │   │ (GitOps Policy Engine)   │
└─────────────────────────┘   └──────────────────────────┘
```

#### Komponen Arsitektur Utama:

1. **Identity & Token Topology (RFC 9068 & RFC 8693):**
   * Di tingkat edge, gateway menerima *Opaque Token* atau *Public JWT*.
   * Menggunakan pola **Token Exchange (RFC 8693)**, Edge Gateway menukar token eksternal menjadi *cryptographically signed internal JWT* (RFC 9068) yang disederhanakan dan dibubuhi *claim* spesifik domain internal (downscoping scopes, user tenancy, user roles).
   * Menghindari *Confused Deputy Problem* dengan menyematkan `aud` (Audience) target mikroservis secara deterministik.

2. **Policy Enforcement Point (PEP) vs Policy Decision Point (PDP):**
   * **PEP (Envoy/Go Middleware):** Menghentikan aliran request, mengekstrak konteks (subjek, aksi, objek, atribut lingkungan), mengirimkan *query context* ke PDP, dan mengeksekusi aksi (`ALLOW` / `DENY`).
   * **PDP (Open Policy Agent - OPA):** Mesin inferensi logika *in-memory* yang mengevaluasi aturan yang ditulis dalam bahasa Rego. OPA berjalan sebagai *sidecar daemon* (akses via Unix Domain Socket atau Localhost gRPC) untuk mengeliminasi *network hop latency* eksternal.

3. **Data Plane Cryptography & mTLS Lifecycle:**
   * Setiap *workload* mikroservis dialokasikan identitas kriptografis menggunakan *SPIFFE IDs* (misalnya: `spiffe://prod.internal/ns/payment/sa/processor`).
   * Sertifikat X.509 SVID (*SPIFFE Verifiable Identity Document*) dirotasi secara otomatis dengan masa berlaku pendek (*short-lived*, misal: 1 jam) guna memitigasi kebocoran private key tanpa bergantung pada *CRL (Certificate Revocation Lists)* atau *OCSP Stapling* internal yang lambat.

4. **Distributed Dynamic Rate Limiting Engine:**
   * Menggunakan algoritma **Sliding Window Counter** terdistribusi di atas Redis Cluster. 
   * Mencegah eksploitasi Resource Exhaustion (OWASP API4) menggunakan kombinasi parameter: `API Key + Client IP + Target Route + Cost Weight`.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Legacy Monolith) | Pendekatan Enterprise Zero-Trust (Modern) |
| :--- | :--- | :--- |
| **Trust Model** | Perimeter-based (Jaringan internal dianggap aman) | Zero-Trust (Semua node tidak tepercaya, verifikasi eksplisit) |
| **Otorisasi** | *Role-Based Access Control* (RBAC) statis hard-coded | *Attribute-Based* (ABAC) & *Relationship-Based* (ReBAC) dinamis via Policy-as-Code |
| **Token Handling** | JWT gemuk (*fat JWT*) diteruskan dari edge ke semua internal services | Edge Token Exchange; token internal minimal, short-lived, target-scoped |
| **Service Identity**| Alamat IP statis / Firewall rules | SPIFFE/SPIRE kriptografis mTLS identities |
| **Governance** | Manual spreadsheet reviews, *ad-hoc* documentation | Automated GitOps linters (Spectral), drift detection, schema-registry contracts |

**Mengapa OPA dan Policy-as-Code?**
Memasukkan aturan otorisasi ke dalam kode sumber aplikasi (*application source code*) menimbulkan *technical debt*, inkonsistensi antar-bahasa pemrograman, dan ketidakmampuan tim audit keamanan untuk memverifikasi kebijakan tanpa memeriksa ribuan baris kode bisnis. Menjadikan otorisasi sebagai *decoupled service* berbasis deklaratif (Rego) memungkinkan verifikasi formal, pengujian unit kebijakan (*policy unit-testing*), dan *auditability* langsung dari repositori Git.

---

### 5. How (Workflow Detail)

Alur verifikasi keamanan request dari ingress hingga eksekusi mikroservis:

```
[Client]              [Edge Gateway]            [Local Envoy PEP]       [Local OPA PDP]        [Domain Core]
    │                        │                         │                       │                     │
    │── 1. POST /v1/orders ──►│                         │                       │                     │
    │   (Bearer Token + Sign)│                         │                       │                     │
    │                        │── 2. Introspect & ─────►│                       │                     │
    │                        │      Token Exchange     │                       │                     │
    │                        │      (Issue Pod JWT)    │                       │                     │
    │                        │── 3. Route via mTLS ───►│                       │                     │
    │                        │   (SPIFFE Header + TLS) │                       │                     │
    │                        │                         │── 4. Query Policy ───►│                     │
    │                        │                         │      (Payload Context)│                     │
    │                        │                         │                       │── 5. Eval Rego ────┐│
    │                        │                         │                       │      Rules in-mem  ││
    │                        │                         │                       │◄───────────────────┘│
    │                        │                         │◄─ 6. Decision Result ─│                     │
    │                        │                         │   (Allow + Mutations) │                     │
    │                        │                         │── 7. Proxy Request ────────────────────────►│
    │                        │                         │      (Sanitized Context)                    │
    │                        │                         │                                             │
    │                        │                         │◄─ 8. Domain Response ───────────────────────│
    │                        │◄─ 9. Return Response ───│                                             │
    │◄─ 10. Send Final JSON ─│
```

1. **Ingress Stage:** Klien mengirimkan HTTP/2 POST request disertai *Access Token* dan header tanda tangan payload (`X-Signature`).
2. **Edge Processing:** Gateway memvalidasi sertifikat mTLS publik (jika B2B), memverifikasi integritas payload, menjalankan rate limiting via Redis, dan menukar token klien dengan *Internal Scoped Token*.
3. **Transport Layer:** Request diteruskan melintasi jaringan mesh menggunakan TLS 1.3 dengan *mutual authentication* (validasi SPIFFE ID).
4. **Service PEP Interception:** Envoy Proxy pada pod penerima mengintersepsi traffic, mengekstraksi path, method, internal JWT claims, dan body hash.
5. **PDP Evaluation:** Envoy memanggil OPA via local gRPC channel. OPA mencocokkan atribut user, data *tenant*, jam akses, serta kepemilikan resource target (*Object Ownership*).
6. **Decision Enforcement:** Bila evaluasi OPA menghasilkan `allow == false`, PEP langsung mengembalikan status `HTTP 403 Forbidden` terstruktur (RFC 7807) tanpa menyentuh *runtime* aplikasi.
7. **Business Execution:** Bila diizinkan, request dialirkan ke aplikasi Go lokal melalui Unix Domain Socket atau localhost.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengamanan Kompleks Konsulat Diplomatik
Bayangkan sistem keamanan konsulat diplomatik dengan proteksi tinggi:
1. **Edge API Gateway (Gerbang Terluar):** Pos penjaga depan memeriksa paspor (Token) Anda. Paspor Anda ditahan, dan Anda diberi *Badge Tamu Sementara* berkode warna khusus (Token Exchange) yang hanya berlaku untuk lantai dan ruangan tertentu, dengan masa aktif 30 menit.
2. **mTLS (Pengawalan Khusus):** Setiap koridor hanya bisa dimasuki jika ada pengawal diplomatik resmi (Envoy Mesh) yang mencocokkan pin biometrik (SPIFFE SVID) di setiap pintu geser baja.
3. **OPA PDP (Dewan Protokoler Tersegel):** Penjaga pintu ruangan tidak memutuskan sendiri apakah Anda boleh masuk. Dia mengangkat interkom terisolasi ke *Dewan Protokoler* (OPA), "Pengunjung X dengan badge tipe Y ingin melihat berkas Z pada jam 14:00, apakah boleh?". Dewan memeriksa buku regulasi (Rego) dan menjawab "Boleh, tetapi berkas sensitif halaman 4 harus disensor" (Data Masking).

```
+-----------------------------------------------------------------------------------------+
|                                    ZERO-TRUST BOUNDARY                                  |
|                                                                                         |
|  [External Client]                                                                      |
|          │                                                                              |
|          │ HTTPS (TLS 1.3)                                                              |
|          ▼                                                                              |
|  +--------------------+                                                                 |
|  | EDGE API GATEWAY   |                                                                 |
|  |  +---------------+ |                                                                 |
|  |  | Rate Limiter  | |                                                                 |
|  |  +-------┬-------+ |                                                                 |
|  |          ▼         |                                                                 |
|  |  | Token Exchanger |                                                                 |
|  +----------┬---------+                                                                 |
|             │                                                                           |
|             │ mTLS (SPIFFE Identity Verification)                                       |
|             ▼                                                                           |
|  +-----------------------------------------------------------------------------------+  |
|  | KUBERNETES POD BOUNDARY                                                           |  |
|  |                                                                                   |  |
|  |  +-------------------------+                 +----------------------------------+ |  |
|  |  | Envoy Proxy (PEP)       |                 | Open Policy Agent (PDP)          | |  |
|  |  |                         |  Local Loopback |  +-----------------------------+ | |  |
|  |  | - Verify SPIFFE Client  |───── gRPC ─────►|  | In-Memory Compiled Rego     | | |  |
|  |  | - Extract JWT Context   |                 |  | Policies & Data Cache       | | |  |
|  |  +------------┬------------+                 +----------------------------------+ |  |
|  |               │ Request Allowed                                                   |  |
|  |               ▼ (Localhost HTTP/UDS)                                              |  |
|  |  +-------------------------+                                                      |  |
|  |  | Go Core Application     |                                                      |  |
|  |  | (Business Logic Layer)  |                                                      |  |
|  |  +-------------------------+                                                      |  |
|  +-----------------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: RFC 7807 Enterprise Standard Error Representation
Respons error keamanan tidak boleh membocorkan *stack trace* atau topologi internal, namun wajib memiliki *audit fingerprint*.

```json
{
  "type": "https://api.enterprise.com/errors/authorization-failure",
  "title": "Forbidden Access",
  "status": 403,
  "detail": "Subject does not possess dynamic attribute 'account:write' for resource 'acc_928341'.",
  "instance": "/v1/accounts/acc_928341/transfers",
  "code": "ERR_AUTHZ_BOLA_VIOLATION",
  "trace_id": "0af7651916cd43dd8448eb211c80319c",
  "timestamp": "2026-03-30T10:14:00.523Z"
}
```

#### B. Practical Example: Production-Grade Security Middleware & OPA Evaluation Engine (Go)

Struktur ini mendemonstrasikan implementasi *Policy Enforcement Point (PEP)* performa tinggi yang memvalidasi internal token, mengekstrak konteks objek bisnis, dan meminta evaluasi ke OPA *in-process engine*.

```go
package security

import (
	"context"
	"crypto/rsa"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/open-policy-agent/opa/rego"
)

// InternalClaims merepresentasikan payload JWT yang telah ditransformasikan di Gateway
type InternalClaims struct {
	TenantID string   `json:"tid"`
	Roles    []string `json:"roles"`
	UserID   string   `json:"sub"`
	jwt.RegisteredClaims
}

// SecurityContext berisi konteks yang diinjeksi ke request context Go
type SecurityContext struct {
	UserID   string
	TenantID string
	Roles    []string
}

type contextKey string

const SecurityCtxKey contextKey = "security_context"

type EnterpriseSecurityPEP struct {
	publicKey   *rsa.PublicKey
	regoQuery   rego.PreparedEvalQuery
	mu          sync.RWMutex
}

// Inisialisasi PEP Engine dengan OPA Query yang telah dikompilasi sebelumnya (pre-compiled)
func NewEnterpriseSecurityPEP(ctx context.Context, rsaPubKey *rsa.PublicKey, regoPolicy string) (*EnterpriseSecurityPEP, error) {
	query, err := rego.New(
		rego.Query("data.enterprise.authz.allow"),
		rego.Module("enterprise_authz.rego", regoPolicy),
	).PrepareForEval(ctx)

	if err != nil {
		return nil, fmt.Errorf("gagal mengompilasi OPA policy: %w", err)
	}

	return &EnterpriseSecurityPEP{
		publicKey: rsaPubKey,
		regoQuery: query,
	}, nil
}

// Middleware mengimplementasikan HTTP PEP Engine
func (pep *EnterpriseSecurityPEP) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		// 1. Ekstraksi dan Validasi Authorization Header
		authHeader := r.Header.Get("Authorization")
		if !strings.HasPrefix(authHeader, "Bearer ") {
			pep.writeRFC7807(w, http.StatusUnauthorized, "ERR_MISSING_TOKEN", "Authorization token tidak ditemukan.")
			return
		}

		rawToken := strings.TrimPrefix(authHeader, "Bearer ")
		claims := &InternalClaims{}

		parsedToken, err := jwt.ParseWithClaims(rawToken, claims, func(t *jwt.Token) (interface{}, error) {
			if _, ok := t.Method.(*jwt.SigningMethodRSA); !ok {
				return nil, fmt.Errorf("signing method tidak valid: %v", t.Header["alg"])
			}
			return pep.publicKey, nil
		})

		if err != nil || !parsedToken.Valid {
			pep.writeRFC7807(w, http.StatusUnauthorized, "ERR_INVALID_TOKEN", "Token kriptografis tidak valid atau expired.")
			return
		}

		// 2. Siapkan Context Input untuk Evaluasi OPA (ABAC context)
		evalInput := map[string]interface{}{
			"user": map[string]interface{}{
				"id":        claims.UserID,
				"tenant_id": claims.TenantID,
				"roles":     claims.Roles,
			},
			"action": r.Method,
			"path":   r.URL.Path,
			"tenant": claims.TenantID,
		}

		// 3. Evaluasi Policy (In-Memory PDP)
		results, err := pep.regoQuery.Eval(r.Context(), rego.EvalInput(evalInput))
		if err != nil {
			pep.writeRFC7807(w, http.StatusInternalServerError, "ERR_PDP_FAILURE", "Kegagalan evaluasi engine otorisasi.")
			return
		}

		if len(results) == 0 || !results[0].Bindings["data.enterprise.authz.allow"].(bool) {
			pep.writeRFC7807(w, http.StatusForbidden, "ERR_AUTHZ_FORBIDDEN", "Kebijakan keamanan menolak akses ke resource ini.")
			return
		}

		// 4. Inject Security Context dan Lanjutkan ke Business Handler
		secCtx := SecurityContext{
			UserID:   claims.UserID,
			TenantID: claims.TenantID,
			Roles:    claims.Roles,
		}

		r = r.WithContext(context.WithValue(r.Context(), SecurityCtxKey, secCtx))
		w.Header().Set("X-Authz-Latency-Microseconds", fmt.Sprintf("%d", time.Since(start).Microseconds()))

		next.ServeHTTP(w, r)
	})
}

func (pep *EnterpriseSecurityPEP) writeRFC7807(w http.ResponseWriter, status int, code, detail string) {
	w.Header().Set("Content-Type", "application/problem+json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"type":      fmt.Sprintf("https://api.enterprise.com/errors/%s", strings.ToLower(code)),
		"title":     http.StatusText(status),
		"status":    status,
		"detail":    detail,
		"code":      code,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}
```

#### Rego Policy Engine Definition (`enterprise_authz.rego`):

```rego
package enterprise.authz

import future.keywords.in

default allow = false

# Whitelist endpoint dokumentasi publik
allow {
    input.path == "/v1/openapi.json"
    input.action == "GET"
}

# Role-Based & Tenant Validation
allow {
    # Validasi kesesuaian tenant
    input.user.tenant_id == input.tenant
    
    # Path extraction: /v1/organizations/{org_id}/billing
    regex.match("^/v1/organizations/([^/]+)/billing$", input.path)
    
    # Hanya role finance atau cluster-admin yang boleh mengakses
    some role in input.user.roles
    role in ["FINANCE_ADMIN", "SECURITY_AUDITOR"]
    
    # Mencegah operasi destruktif selain audit
    input.action in ["GET", "HEAD"]
}

# Mencegah BOLA (Broken Object Level Authorization) pada resource milik user
allow {
    regex.match("^/v1/users/([^/]+)/profile$", input.path)
    [_, path_user_id] := regex.find_string_submatch("^/v1/users/([^/]+)/profile$", input.path)
    
    # Subject token ID harus identik dengan resource URI
    input.user.id == path_user_id
    input.action in ["GET", "PUT", "PATCH"]
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Penetrasi Data Akun dan BOLA Migration pada Platform Transaksi Finansial Tier-1 (50.000 RPS)

* **Skala Sistem:** Platform FinTech memproses 50.000 RPS peak, mengelola 40 juta akun aktif, berbasis Kubernetes multi-cluster (AWS EKS & On-Premise Data Center).
* **Insiden:** Audit internal menemukan celah **OWASP API 1: BOLA** di mana parameter `account_id` pada endpoint `/api/v2/accounts/{account_id}/statement` dapat dimanipulasi oleh penyerang dengan mengubah ID numerik sekuensial. Layanan mikro hilir mempercayai header `X-User-ID` yang diteruskan oleh reverse-proxy legacy tanpa validasi tanda tangan kriptografi atau kepemilikan resource runtime.

#### Solusi Arsitektural yang Diterapkan:
1. **Penerapan SPIFFE/SPIRE dan Envoy Internal Mesh:**
   * Diinstal SPIRE Server untuk mendistribusikan sertifikat X.509 mikroservis secara otomatis. Komunikasi antar Pod diisolasi oleh Envoy dengan enkripsi mTLS.
2. **Kriptografi Context Propagation:**
   * Gateway menanggalkan seluruh header tidak terpercaya (`X-User-*`). Gateway menerbitkan **Short-lived RFC 9068 Cryptographic JWT** (masa aktif 120 detik) yang ditandatangani menggunakan algoritma asymmetric curve ES384.
3. **Desentralisasi Policy Engine (OPA Sidecar):**
   * Alih-alih memanggil centralized auth service yang dapat menciptakan *single point of failure* dan menambah latensi $20\text{ ms}$, sebuah sidecar OPA diinjeksikan pada setiap pod backend.
   * Dataset identitas pemilik akun (*Account Ownership Inverted Index*) disinkronisasi ke memori OPA menggunakan OPA Bundle APIs yang diperbarui secara *streaming* via Kafka topic terkompresi.

#### Metrik Evaluasi:
* **Overhead Latensi PDP:** Evaluasi Rego in-memory menghasilkan $p99 < 1.1\text{ ms}$.
* **Throughput:** Sistem mempertahankan kapasitas $50.000\text{ RPS}$ tanpa lonjakan alokasi memori yang signifikan.
* **Hasil Audit:** Kerentanan BOLA sepenuhnya tertutup. Skenario *unauthorized resource access* langsung diputus di Envoy sidecar dengan return `HTTP 403 Forbidden` dan peringatan otomatis ke SIEM SOC.

---

### 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **In-Memory OPA Engine (Sidecar)** | Latensi evaluasi ultra-rendah ($< 1\text{ ms}$), toleran terhadap kegagalan jaringan luar pod. | Konsumsi Resource RAM Pod meningkat (setiap pod menampung bundle data); replikasi data ke ribuan pod memakan overhead jaringan cluster. |
| **Remote Centralized PDP API** | Manajemen konsistensi data otorisasi terpusat secara mutlak (*single source of truth*), tanpa jejak memori lokal di pod. | Latensi jaringan bertambah ($+15 - 30\text{ ms}$ roundtrip), cascading failure risiko tinggi bila cluster PDP kelebihan beban. |
| **mTLS dengan Validasi Sertifikat Penuh** | Zero-trust mutlak pada level L4/L7, pencegahan *man-in-the-middle* (MitM) sempurna di dalam data center. | CPU cost handshake bertambah (diperlukan TLS Session Resumption & Hardware Offloading AES-NI), kompleksitas manajemen sertifikat (SPIFFE CA/PKI engine). |
| **Sliding Window Counter Terdistribusi (Redis)** | Akurasi tinggi dalam mencegah burst rate limiting; tidak memiliki boundary reset problem seperti *Fixed Window*. | Latensi tambahan ($+1 - 2\text{ ms}$) ke Redis cluster pada setiap request; dependensi operasional pada availability cluster Redis. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Mengandalkan Claims JWT Client Tanpa Re-Validation Data Layer
* **Kesalahan:** Microservice menerima klaim JWT `role: "admin"` dari edge tanpa memvalidasi apakah status admin subjek telah dicabut (*revoked*) dalam database transaksional.
* **Mitigasi:** Kombinasikan JWT berumur super-pendek (*short-lived*, misal 5 menit) dengan *Revocation List* (CRL berbasis bloom-filter cepat) yang didistribusikan ke local cache OPA.

#### 2. Clock Skew Authentication Failure
* **Gejala:** Muncul error `Token is not valid yet (nbf)` atau `Token has expired (exp)` secara intermiten pada multi-node cluster.
* **Root Cause:** Drift waktu antar-server melebihi batas toleransi mesin kriptografis.
* **Solusi:** Konfigurasikan library JWT parser dengan toleransi jeda waktu (*leeway*) sebesar $30 - 60\text{ detik}$, serta pasang NTP daemon (Chrony) dengan sinkronisasi ke atomic clock provider di seluruh node cluster.

#### 3. Kebocoran Metadata Internal via Error Body (Information Leakage)
* **Gejala:** Ketika OPA atau database backend menolak eksekusi, gateway mengembalikan log internal database SQL atau stack trace Go.
* **Solusi:** Gunakan middleware recovery terpadu yang memetakan error internal ke representasi standar RFC 7807 tanpa ekspos nama tabel, query, IP, atau runtime version.

#### Panduan Troubleshooting Otentikasi:
```bash
# 1. Periksa validity dan detail masa aktif sertifikat internal SPIFFE mTLS
openssl s_client -connect microservice-payment.internal:443 -showcerts \
  -servername microservice-payment.internal < /dev/null

# 2. Decode dan verifikasi Header & Payload JWT secara manual di CLI
echo "<jwt_token>" | cut -d'.' -f2 | base64 -d | jq .

# 3. Debug evaluasi OPA via Unix Socket menggunakan input payload langsung
curl --unix-socket /var/run/opa/opa.sock http://localhost/v1/data/enterprise/authz/allow \
  -H "Content-Type: application/json" \
  -d '{"input": {"user": {"id": "usr_test", "roles": ["ANALYST"]}, "action": "DELETE", "path": "/v1/data"}}'
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Enforce TLS 1.3 Only:** Nonaktifkan TLS 1.0, 1.1, dan 1.2 di seluruh Ingress Edge Gateway. Wajibkan penggunaan *cipher suites* yang memiliki forward secrecy (`TLS_AES_128_GCM_SHA256` atau `TLS_AES_256_GCM_SHA384`).
- [ ] **Contract-Driven Governance via CI/CD:** Jalankan *Spectral Linter* untuk validasi spesifikasi OpenAPI/AsyncAPI pada setiap pull-request:
  - Wajib memiliki `securitySchemes` yang seragam.
  - Melarang properti camelCase/snakeCase yang bercampur (*case style enforcement*).
  - Melarang ekspos entitas database mentah secara eksplisit.
- [ ] **Detect Breaking Changes:** Gunakan *oasdiff* di pipeline CI untuk memblokir pull request jika terdapat perubahan melanggar kompatibilitas (penghapusan field, perubahan format data, mutasi status code).
- [ ] **Audience (`aud`) Strict Validation:** Setiap token internal wajib mencantumkan identitas servis penerima secara spesifik guna memitigasi *Token Relaying Attack*.
- [ ] **Prevent Parameter Pollution & Mass Assignment:** Terapkan skema deserialisasi Go yang menolak field yang tidak didefinisikan (`disallowUnknownFields`).
- [ ] **Rotasi Secret Kriptografi Berkala:** Integrasikan Gateway dengan HashiCorp Vault atau AWS Secrets Manager untuk rotasi kunci privat signing JWT secara terjadwal tanpa *downtime*.

---

### 12. Hands-on Practice

Buat dan simpan seluruh berkas praktikum di direktori: `hands-on/m02/`

#### Langkah 1: Siapkan Struktur File
```bash
mkdir -p hands-on/m02/{policy,certs,app}
cd hands-on/m02/
```

#### Langkah 2: Buat Kebijakan Rego (`policy/authz.rego`)
```rego
package enterprise.security

default allow = false

allow {
    input.method == "GET"
    input.path == "/healthz"
}

allow {
    input.method == "GET"
    regex.match("^/accounts/[^/]+$", input.path)
    claims := input.jwt_claims
    claims.role == "auditor"
}

allow {
    input.method == "POST"
    input.path == "/transfers"
    claims := input.jwt_claims
    claims.role == "operator"
    input.body.amount <= 10000000
}
```

#### Langkah 3: Setup Docker Compose (`docker-compose.yaml`)
Setup terintegrasi OPA Sidecar, Redis Rate-Limiter, dan mock Go App.

```yaml
version: '3.8'

services:
  opa:
    image: openpolicyagent/opa:0.68.0
    command:
      - "run"
      - "--server"
      - "--addr=0.0.0.0:8181"
      - "/policies"
    volumes:
      - ./policy:/policies
    ports:
      - "8181:8181"

  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"

  app-service:
    build:
      context: ./app
    ports:
      - "8080:8080"
    environment:
      - OPA_ENDPOINT=http://opa:8181/v1/data/enterprise/security/allow
      - REDIS_ADDR=redis:6379
    depends_on:
      - opa
      - redis
```

#### Langkah 4: Implementasi App Server Mock (`app/main.go`)
```go
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
)

var (
	rdb         *redis.Client
	opaEndpoint string
)

func main() {
	opaEndpoint = os.Getenv("OPA_ENDPOINT")
	if opaEndpoint == "" {
		opaEndpoint = "http://localhost:8181/v1/data/enterprise/security/allow"
	}

	redisAddr := os.Getenv("REDIS_ADDR")
	if redisAddr == "" {
		redisAddr = "localhost:6379"
	}

	rdb = redis.NewClient(&redis.Options{Addr: redisAddr})

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"HEALTHY"}`))
	})
	mux.HandleFunc("/accounts/", handleAccounts)
	mux.HandleFunc("/transfers", handleTransfers)

	server := &http.Server{
		Addr:         ":8080",
		Handler:      enforceSecurityPEP(mux),
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	log.Println("Microservice berjalan di port 8080...")
	log.Fatal(server.ListenAndServe())
}

func enforceSecurityPEP(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()

		// Sederhana: Bypass rate-limiting dan auth untuk endpoint healthcheck
		if r.URL.Path == "/healthz" {
			next.ServeHTTP(w, r)
			return
		}

		// 1. Sliding Window Rate Limiting (Redis)
		clientIP := strings.Split(r.RemoteAddr, ":")[0]
		key := fmt.Sprintf("rate:%s:%d", clientIP, time.Now().Unix()/60)
		count, err := rdb.Incr(ctx, key).Result()
		if err == nil && count == 1 {
			rdb.Expire(ctx, key, 65*time.Second)
		}
		if count > 60 { // Limit 60 rpm
			http.Error(w, `{"error":"RATE_LIMIT_EXCEEDED"}`, http.StatusTooManyRequests)
			return
		}

		// 2. Parse Mock Context Token
		role := r.Header.Get("X-Mock-Role")

		var bodyBytes []byte
		if r.Body != nil {
			bodyBytes, _ = io.ReadAll(r.Body)
			r.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))
		}

		var bodyJSON interface{}
		_ = json.Unmarshal(bodyBytes, &bodyJSON)

		// 3. Evaluasi OPA PDP
		opaPayload := map[string]interface{}{
			"input": map[string]interface{}{
				"method": r.Method,
				"path":   r.URL.Path,
				"jwt_claims": map[string]interface{}{
					"role": role,
				},
				"body": bodyJSON,
			},
		}

		opaBytes, _ := json.Marshal(opaPayload)
		resp, err := http.Post(opaEndpoint, "application/json", bytes.NewBuffer(opaBytes))
		if err != nil {
			http.Error(w, `{"error":"SECURITY_ENGINE_UNAVAILABLE"}`, http.StatusInternalServerError)
			return
		}
		defer resp.Body.Close()

		var opaResponse struct {
			Result bool `json:"result"`
		}
		_ = json.NewDecoder(resp.Body).Decode(&opaResponse)

		if !opaResponse.Result {
			http.Error(w, `{"error":"FORBIDDEN_BY_POLICY"}`, http.StatusForbidden)
			return
		}

		next.ServeHTTP(w, r)
	})
}

func handleAccounts(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"account_id":"acc_123","balance":50000000}`))
}

func handleTransfers(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"status":"SUCCESS","transaction_id":"tx_891238"}`))
}
```

#### Langkah 5: Eksekusi Pengujian
```bash
# Jalankan environment
docker-compose up --build -d

# Test 1: Healthcheck (Bypass - Harus 200 OK)
curl -i http://localhost:8080/healthz

# Test 2: Akses Accounts tanpa role memadai (Harus 403 Forbidden)
curl -i -H "X-Mock-Role: guest" http://localhost:8080/accounts/acc_123

# Test 3: Akses Accounts dengan role auditor (Harus 200 OK)
curl -i -H "X-Mock-Role: auditor" http://localhost:8080/accounts/acc_123

# Test 4: Eksekusi Transfer Melebihi Limit Rego Policy (15 Juta) (Harus 403 Forbidden)
curl -i -X POST http://localhost:8080/transfers \
  -H "X-Mock-Role: operator" \
  -H "Content-Type: application/json" \
  -d '{"amount": 15000000}'
```

---

### 13. Exercise

#### Level: Easy
1. Modifikasi file `policy/authz.rego` agar mengizinkan request `GET` ke endpoint `/v1/audit-logs` hanya jika request membawa header `X-Mock-Role: compliance_officer`. Uji menggunakan `curl` dan periksa status responsnya.

#### Level: Medium
1. Implementasikan middleware di Go untuk mendeteksi *replay attack* pada endpoint `/transfers`. Setiap request wajib menyertakan header `X-Idempotency-Key` (UUIDv4) dan `X-Timestamp` (UNIX Milliseconds). 
2. Request harus ditolak jika:
   - Nilai waktu (`X-Timestamp`) memiliki selisih *clock skew* $> 60\text{ detik}$ dari waktu sistem server.
   - Kunci `X-Idempotency-Key` ditemukan duplikat di Redis dalam jendela waktu validitas 10 menit.

#### Level: Hard
1. Buat ekstensi integrasi Envoy Proxy yang menggunakan filter `envoy.filters.http.ext_authz`. Hubungkan Envoy langsung ke OPA via gRPC interface (port 9191) tanpa menyentuh layer kode aplikasi Go sama sekali. Buktikan melalui access log Envoy bahwa request yang ditolak OPA tidak pernah diteruskan ke upstream container.

---

### 14. Challenge

**Skenario Kasus Produksi Riil:**
Sebuah holding conglomerate keuangan mengakuisisi platform e-commerce regional. Anda ditunjuk sebagai Principal Architect untuk merancang arsitektur **Cross-Cloud Token Mediation & Distributed Governance** dengan parameter tantangan berikut:

1. **Topologi:** Ingress utama berada di Google Cloud Platform (Apigee Enterprise), sedangkan inti komputasi perbankan berada di On-Premises Mainframe yang dibungkus oleh Kubernetes Mesh.
2. **Kondisi:** Edge Gateway menerbitkan JWT beralgoritma `RS256` yang ditandatangani oleh Google Cloud KMS. Sistem inti on-premises menolak sertifikat luar dan hanya menerima token berformat `PASETO v4.local` (Symmetric encryption) atau internal short-lived JWT yang ditandatangani oleh internal HashiCorp Vault PKI (Elliptic Curve `ES384`).
3. **Persyaratan Latensi:** Overhead pemrosesan keamanan total (validasi edge, translasi token, inspeksi mTLS SPIFFE, dan evaluasi PDP ABAC) tidak boleh melebihi $8\text{ ms}$ pada persentil ke-99.
4. **Tantangan Arsitektur:** Rancang dokumen blueprint teknis yang memetakan:
   - Desain aliran pertukaran token (*Token Translation Gateway Layer*).
   - Mitigasi bila sirkuit koneksi data center inter-cloud terputus sebagian (*split-brain/partial network partition*).
   - Strategi audit tak terbantahkan (*non-repudiation log*) yang membuktikan tidak ada data nasabah bocor antar-entitas anak perusahaan.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (Pilihan Ganda)
1. Apa kelemahan utama dari paradigma keamanan jaringan perimeter (*Perimeter-Based Security*)?
   - A. Mengharuskan enkripsi data at-rest.
   - B. Asumsi bahwa seluruh entitas di dalam jaringan privat aman dan dapat dipercaya (*implicit trust*).
   - C. Terlalu bergantung pada OPA.
   - D. Hanya dapat berjalan menggunakan HTTP/1.1.

2. RFC yang mengatur representasi standar respons error API adalah:
   - A. RFC 6749
   - B. RFC 7519
   - C. RFC 7807
   - D. RFC 8414

3. Komponen dalam arsitektur otorisasi yang bertugas membuat keputusan kebijakan (*Policy Decision*) adalah:
   - A. PEP (Policy Enforcement Point)
   - B. PDP (Policy Decision Point)
   - C. PKI (Public Key Infrastructure)
   - D. WAF (Web Application Firewall)

4. Algoritma rate-limiting yang paling presisi dalam mengatasi lonjakan (*burst*) di perbatasan menit tanpa *reset boundary flaw* adalah:
   - A. Fixed Window Counter
   - B. Sliding Window Counter
   - C. Simple Round Robin
   - D. Least Connection

5. Identitas beban kerja (*workload identity*) dalam arsitektur Cloud-Native SPIFFE dinyatakan dalam format:
   - A. IPv6 static address
   - B. URI SPIFFE ID yang dikodekan ke dalam Subject Alternative Name (SAN) sertifikat X.509
   - C. API Key terenkripsi SHA256
   - D. Basic Authentication header

#### B. Pertanyaan Intermediate (Pilihan Ganda & Analisis)
6. Manakah yang **bukan** merupakan mitigasi langsung terhadap kerentanan OWASP API 1: Broken Object Level Authorization (BOLA)?
   - A. Mengompresi payload respons JSON menggunakan Brotli.
   - B. Memvalidasi kepemilikan resource ID secara dinamis terhadap subjek JWT di PDP OPA.
   - C. Mengganti ID numerik berurutan (*sequential auto-increment*) dengan UUIDv4 kriptografis.
   - D. Menerapkan kontrol akses ABAC yang membandingkan `tenant_id` subjek dan objek target.

7. Apa tujuan utama diterapkannya RFC 8693 (OAuth 2.0 Token Exchange) di level API Gateway?
   - A. Menghapus kebutuhan enkripsi TLS.
   - B. Menukar token publik/klien menjadi token internal yang memiliki scope minimum, masa berlaku singkat, dan target audience terbatas.
   - C. Mempercepat koneksi TCP database.
   - D. Mengubah format payload JSON menjadi XML secara transparan.

8. Mengapa OPA engine paling optimal dijalankan sebagai *sidecar pod* atau library *in-process*, alih-alih sebagai cluster sentral terpusat di luar cluster data?
   - A. Karena OPA tidak mendukung protokol TCP.
   - B. Untuk menghilangkan network overhead hop dan mencegah kegagalan sistem terpusat (*single point of failure*).
   - C. Karena bahasa Rego tidak bisa dikompilasi secara paralel.
   - D. Agar data kebijakan disimpan permanen di hard disk lokal pod.

9. Jika clock skew antara mesin otorisasi dan token issuer terpaut 45 detik lebih cepat di sisi penerima, error apa yang paling sering muncul jika parser tidak memiliki parameter leeway?
   - A. `token_malformed`
   - B. `token_signature_invalid`
   - C. `token_not_yet_valid` (nbf constraint)
   - D. `algorithm_mismatch`

10. Apa fungsi dari klaim `aud` (Audience) di dalam payload JSON Web Token terstandarisasi (RFC 7519)?
    - A. Menyimpan IP address dari klien asal.
    - B. Mengidentifikasi penerima atau sistem mikroservis spesifik yang berhak memproses token tersebut.
    - C. Menghitung jumlah panggilan API yang dilakukan pengguna.
    - D. Menentukan durasi cache memori Redis.

#### C. Skenario Kasus Produksi
11. **Skenario 1:** Tim Operasional melaporkan bahwa latensi API Gateway melonjak dari $p99 = 4\text{ ms}$ menjadi $p99 = 280\text{ ms}$ setelah mengaktifkan verifikasi JWT pada 30.000 RPS. Kode gateway melakukan panggilan HTTPS ke endpoint JWKS (`/.well-known/jwks.json`) identity provider pada setiap request yang masuk. Apa akar masalahnya dan bagaimana desain arsitektur perbaikannya?

12. **Skenario 2:** Sebuah financial microservice menerapkan otorisasi RBAC berbasis klaim JWT `role: "admin"`. Seorang karyawan telah diturunkan perannya (*revoked*) dari sistem manajemen karyawan, namun token JWT yang dimilikinya masih berlaku selama 4 jam ke depan. Karyawan tersebut tetap dapat mengeksekusi operasi penghapusan data. Bagaimana Anda merancang mitigasi sistemik tanpa menurunkan durasi kedaluwarsa token menjadi 1 detik?

13. **Skenario 3:** Tim penguji penetrasi (*penetration tester*) berhasil memalsukan identitas request antar-servis internal dengan cara menyuntikkan header `X-Forwarded-For` dan `X-User-Identity` palsu dari luar perimeter gateway. Mengapa gateway Anda meloloskan injeksi ini, dan perubahan aturan arsitektural apa yang wajib diterapkan di layer PEP?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Kunci Pilihan Ganda (Basic & Intermediate):
1. **B** — Model perimeter berasumsi bahwa siapapun yang berada di dalam jaringan intranet adalah pihak terpercaya.
2. **C** — RFC 7807 (Problem Details for HTTP APIs).
3. **B** — PDP bertugas mengevaluasi logika dan atribut untuk menghasilkan keputusan (*decision*).
4. **B** — Sliding Window Counter membagi window menjadi interval halus untuk menghindari pembebanan ganda pada batas interval (*edge reset*).
5. **B** — Standar SPIFFE memetakan URI unik pada ekstensi SAN (Subject Alternative Name) sertifikat X.509.
6. **A** — Kompresi komputasional Brotli tidak memiliki korelasi dengan verifikasi relasi subjek dan objek data.
7. **B** — Token exchange menurunkan privilege token (*downscoping*) serta membatasi radius ledakan (*blast radius*) jika token dicuri.
8. **B** — Evaluasi lokal via memory memotong latensi hingga skala sub-millisecond dan mencegah sistem down serentak jika PDP terpusat gagal.
9. **C** — Waktu `nbf` (Not Before) pada token akan terbaca berada di masa depan oleh node yang jamnya lebih cepat.
10. **B** — Memastikan token tidak disalahgunakan untuk servis internal lain yang bukan peruntukannya (*mitigasi cross-service token replay*).

#### Solusi Skenario Kasus Produksi:
11. **Solusi Skenario 1:**
    * *Root Cause:* Gateway melakukan network roundtrip ke OIDC server JWKS pada setiap request secara tersinkronisasi, memicu *network congestion*, rate limiting dari identity provider, dan lonjakan latensi masif.
    * *Arsitektur Perbaikan:* Terapkan caching JWKS in-memory dengan mekanisme *stale-while-revalidate*. Gateway menyimpan public keys di memori lokal, hanya memperbarui cache saat menerima token dengan `kid` (Key ID) baru yang tidak dikenali atau setelah interval periodik (misal: 12 jam) secara asinkron.
12. **Solusi Skenario 2:**
    * *Solusi Terpadu:* Implementasikan pola **Hybrid Token Revocation**. Simpan status pembatalan identitas (Subject ID atau Session ID) pada Redis Cluster terpusat atau *Bloom Filter array* yang direplikasi via pub/sub ke seluruh PEP sidecar pod. OPA sidecar mengevaluasi dua hal: validitas kriptografi JWT (lokal) dan keberadaan `revocation_id` dalam distributed fast in-memory store.
13. **Solusi Skenario 3:**
    * *Root Cause:* Gateway bertindak sebagai *pass-through proxy* tanpa melakukan sanitasi (*stripping*) terhadap header sensitif dari entitas luar, dan mikroservis hilir tidak berada dalam enkapsulasi mTLS sehingga mengeksekusi request tanpa validasi identitas jaringan.
    * *Mitigasi Arsitektural:*
      1. Gateway wajib secara eksplisit menghapus seluruh header `X-Forwarded-*` dan `X-User-*` yang datang dari interface publik sebelum meneruskannya ke internal.
      2. Terapkan mTLS SPIFFE di level service mesh. Microservice hilir harus menolak semua request yang tidak memiliki identitas kriptografis terpercaya dari cluster Gateway.

---

### 16. Summary

Implementasi API Security & Governance kelas enterprise pada skala cloud-native modern bertransisi dari perimeter-based protection menuju model komprehensif **Zero-Trust**. Pondasi arsitektur ini bertumpu pada decoupling antara **PEP (Policy Enforcement Point)** yang diintegrasikan pada ingress atau sidecar proxy, dan **PDP (Policy Decision Point)** berbasis Policy-as-Code (seperti OPA) yang mengevaluasi context atribut secara in-memory dengan target waktu evaluasi sub-millisecond.

Melalui integrasi otomasi tata kelola (*Governance-as-Code*) pada CI/CD, verifikasi kontrak API berjalan secara paralel dengan penegakan keamanan runtime. Pola modern menuntut penggunaan token scoping yang ketat (RFC 8693/9068), isolasi identitas berbasis mTLS X.509 (SPIFFE/SPIRE), mitigasi komprehensif terhadap celah struktural OWASP API (terutama BOLA/BFLA), serta standardisasi respons insiden berbasis RFC 7807 demi menjaga integritas data tanpa mengorbankan skalabilitas transaksional.