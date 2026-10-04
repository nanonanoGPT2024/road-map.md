# BAB 05: Web App dan API Security
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur Zero Trust Layer 7**: Membangun pipeline autentikasi dan otorisasi terdesentralisasi menggunakan *Sender-Constrained Tokens* (DPoP - RFC 9449 / mTLS RFC 8705) dan *Attribute-Based Access Control* (ABAC) berbasis Open Policy Agent (OPA).
2. **Mitigasi OWASP API Security Top 10 (2023) pada Skala Enterprise**: Mencegah kerentanan kritis seperti *Broken Object Level Authorization* (BOLA/API1), *Broken Object Property Level Authorization* (BOPLA/API3), dan *Server-Side Request Forgery* (SSRF/API7) menggunakan pola desain *egress proxy* dan validasi skema runtime *strict*.
3. **Membangun Pertahanan Distributed Layer-7 DoS & Rate Limiting**: Mengimplementasikan algoritma *Token Bucket* dan *Sliding Window Counter* terdistribusi menggunakan Redis Cluster dengan dukungan *cryptographic proof-of-work challenge*.
4. **Menerapkan Advanced WAF & Runtime Protection**: Mengintegrasikan WebAssembly (WASM) *Security Filters* (Coraza/ModSecurity engine) langsung ke dalam *data plane* Envoy Proxy pada kluster Kubernetes.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Core Cryptography**: Konsep asymmetric encryption (RSA/ECDSA), hashing (SHA-256), HMAC, digital signatures, dan X.509 certificates.
- **Foundational API Security (Module 01)**: OWASP Top 10 dasar, struktur JSON Web Token (JWT - RFC 7519), dan mekanisme CORS/CSP.
- **Networking & System Architecture**: Protokol HTTP/1.1, HTTP/2, TLS 1.3 handshakes, model OSI (Layer 4 vs Layer 7), reverse proxy (Envoy/NGINX), dan container orchestration (Docker & Kubernetes).
- **Bahasa Pemrograman**: Kemahiran membaca dan menulis kode Go (Golang) dan konfigurasi deklaratif (YAML, Rego OPA).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Evolusi Token Security: Bearer vs. Sender-Constrained Tokens
Mayoritas enterprise API saat ini bergantung pada *Bearer Tokens* (RFC 6750). Cacat mendasar dari Bearer Token adalah prinsip kepemilikannya: *siapa pun yang memegang token tersebut dapat menggunakannya* (layaknya uang tunai). Apabila terjadi kebocoran token akibat kompromi memori, *man-in-the-middle* (MITM) via *TLS termination*, log telemetry yang bocor, atau XSS, penyerang dapat langsung melakukan impersonasi tanpa hambatan.

Modul arsitektur lanjutan ini beralih ke **Sender-Constrained Tokens**:
1. **OAuth 2.0 Mutual-TLS Client Certificate-Bound Access Tokens (RFC 8705)**: Token diikat secara kriptografis ke sertifikat X.509 klien yang dinegosiasikan selama *mTLS handshake*. Reverse proxy/API Gateway mencocokkan *fingerprint* sertifikat klien (`x5t#S256`) dengan klaim `cnf` (confirmation) di dalam payload JWT.
2. **OAuth 2.0 Demonstrating Proof-of-Possession (DPoP - RFC 9449)**: Mekanisme level aplikasi di mana klien mengenerate *ephemeral key pair* (biasanya ECDSA P-256). Setiap request HTTP melampirkan header `DPoP` berupa JWT mini yang ditandatangani oleh *private key* klien, mengikat URI, HTTP Method, dan *timestamp*. Backend memvalidasi bahwa pemilik *access token* memegang *private key* yang sama dengan yang didaftarkan saat token diterbitkan.

```
+-----------------------------------------------------------------------------------+
|                           RFC 9449: DPoP Verification                             |
+-----------------------------------------------------------------------------------+
| Client                                         Resource Server (API Gateway/Svc)  |
|   |                                                           |                   |
|   | 1. Generate Ephemeral EC Keypair                          |                   |
|   | 2. Sign DPoP Proof JWT:                                   |                   |
|   |    - htm: "POST"                                          |                   |
|   |    - htu: "https://api.corp.com/v1/transfer"              |                   |
|   |    - jti: "<unique-uuid>"                                 |                   |
|   |    - jwk: <public-key>                                    |                   |
|   |                                                           |                   |
|   | 3. Send Request:                                          |                   |
|   |    Authorization: DPoP <access_token>                     |                   |
|   |    DPoP: <dpop_proof_jwt>                                 |                   |
|   | --------------------------------------------------------> |                   |
|   |                                                           | 4. Validate:      |
|   |                                                           |  a) Verify DPoP   |
|   |                                                           |     Signature     |
|   |                                                           |  b) Check htm/htu |
|   |                                                           |  c) jti replay    |
|   |                                                           |     cache (Redis) |
|   |                                                           |  d) Match 'jkt'   |
|   |                                                           |     in AccessTok  |
|   |                                                           |     with DPoP JWK |
|   | <-------------------------------------------------------- |                   |
|   |             200 OK / 401 Unauthorized                     |                   |
+-----------------------------------------------------------------------------------+
```

#### B. Dynamic Policy Enforcement Engine: Attribute-Based Access Control (ABAC) via OPA
*Role-Based Access Control* (RBAC) gagal menangani BOLA/IDOR (Broken Object Level Authorization) pada skala enterprise karena RBAC hanya memeriksa "*Apakah peran pengguna X boleh memanggil endpoint Y?*", bukan "*Apakah pengguna X memiliki hak akses terhadap entitas Z pada jam ini dari lokasi ini?*".

Arsitektur produksi modern memisahkan logika bisnis dari logika otorisasi dengan pola:
- **PEP (Policy Enforcement Point)**: Envoy Proxy atau Go Middleware API Gateway.
- **PDP (Policy Decision Point)**: Open Policy Agent (OPA) yang mengevaluasi input (user identity, HTTP method, target resource, database context) terhadap deklarasi kebijakan *Rego*.
- **PIP (Policy Information Point)**: Cache kontekstual (misal: Redis) yang menyediakan metadata relasi objek.

#### C. Egress Security Architecture: Blind SSRF Mitigation
SSRF modern menargetkan metadata endpoint cloud (`169.254.169.254`), layanan internal Kubernetes (`kubernetes.default.svc`), atau kontroler orkestrasi internal. Arsitektur backend production-grade memblokir *arbitrary outbound traffic* secara default:
- Backend services dilarang memiliki rute keluar internet langsung (*zero outbound route*).
- Setiap *outbound request* wajib melalui *Hardened Forward Proxy* (misal: Envoy atau Smokescreen) yang melakukan:
  - Resolusi DNS internal dengan pengecekan *IP pinning*.
  - Pemblokiran rentang RFC 1918 (Private IP), RFC 3927 (Link-Local), Loopback (`127.0.0.0/8`), dan Cloud Metadata IPs.
  - Mitigasi *DNS Rebinding Attack* dengan mengevaluasi IP tepat sebelum koneksi TCP dibuat, menonaktifkan *keep-alive connection pooling* untuk host yang tidak tepercaya.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Legacy) | Pendekatan Enterprise Modern (Production Grade) |
| :--- | :--- | :--- |
| **Token Handling** | Static Bearer Tokens (JWT di-sign HS256/RS256). Rentan pencurian token (exfiltration via logs, XSS, SSRF). | **Sender-Constrained Tokens** (DPoP / mTLS RFC 8705). Token dicuri tidak dapat digunakan penyerang tanpa private key klien. |
| **Model Otorisasi** | Hardcoded RBAC di layer aplikasi (`if user.role != 'ADMIN' throw 403`). Rentan BOLA/BOPLA. | **Decoupled ABAC Engine (OPA/Rego)**. Otorisasi mengevaluasi identitas subjek, relasi objek, payload mutasi, dan metadata network. |
| **WAF & Threat Detection** | In-line Appliance sentralistik di depan DMZ. Menyebabkan *bottleneck*, *single point of failure*, dan blind spot terhadap internal traffic. | **Service Mesh Embedded L7 WASM Filters (Coraza Engine)**. Berjalan in-process pada Envoy Proxy sidecar di setiap pod layanan. |
| **Rate Limiting** | In-memory count per IP pada single app instance. Tidak efektif melawan bot terdistribusi dan bypass via spoofed IP. | **Distributed Sliding Window + JA3/JA4 TLS Fingerprinting**. Rate limit berbasis gabungan identitas token, subnet ASN, dan karakteristik cipher handshake TLS. |
| **Deserialization** | Native language unmarshaling langsung ke Generic DTO/Object. Rentan Remote Code Execution (RCE) & Mass Assignment. | **Strict Schema Validation (Protobuf/JSONSchema AST Compiler)** dengan *disallow unknown fields* dan filter *in-flight field-mask*. |

---

### 5. How: Workflow Detail Integrasi Produksi

Alur eksekusi request pada Edge API Gateway dengan standard Zero Trust:

```
[ Client Request ] 
       │
       ▼
[ Layer 4: TLS Termination & JA4 Fingerprinting ]
       │  ├─ Analisis TLS Cipher Suites, Extensions, & ALPN
       │  └─ Cek Blacklist/Reputasi JA4 Fingerprint pada Distributed Cache
       ▼
[ Layer 7: Envoy Proxy Gateway (Data Plane) ]
       │
       ├─► [ Step 1: WAF WASM Engine ]
       │        └─ Evaluasi Core Rule Set (CRS 4.x) terhadap SQLi, XSS, Path Traversal
       │
       ├─► [ Step 2: Distributed Rate Limiting Service (RLS) ]
       │        └─ Cek Sliding Window Token Bucket di Redis (Key: Client ID + IP Subnet)
       │
       ├─► [ Step 3: DPoP Proof Validator ]
       │        ├─ Verifikasi Digital Signature JWT DPoP
       │        ├─ Validasi HTTP Method ('htm') & Target URI ('htu')
       │        ├─ Cek Replay Attack via `jti` nonce di Redis (TTL 300 detik)
       │        └─ Hitung SHA-256 Public Key (jkt) & cocokkan dengan klaim 'cnf.jkt' di Access Token
       │
       ├─► [ Step 4: External Authorization (ext_authz -> OPA Engine) ]
       │        ├─ Parsing JWT Claims
       │        ├─ Parsing Request Body AST (Mendeteksi Mass Assignment / BOPLA)
       │        └─ Evaluasi Rego Policy (PIP: fetch data relasi database bila diperlukan)
       │
       ▼
[ Request Mutator & Egress Sanitizer ]
       │  └─ Hapus DPoP/Sensitive Headers, Inject Internal Identity Context (X-Consumer-ID, X-Roles)
       ▼
[ Upstream Microservices via Internal mTLS (SPIFFE/SPIRE) ]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengambilan Brankas di Bank Eksekutif
- **Bearer Token**: Seperti *Kunci Brankas Fisik Biasa*. Siapa pun yang menemukan kunci tersebut (pencuri, staf pembersih) dapat berjalan ke brankas, memasukkan kunci, dan mengambil uang. Pihak bank tidak tahu siapa yang memegang kunci.
- **Sender-Constrained Token (DPoP)**: Seperti *Kunci Brankas yang Dipasangkan dengan Pemindai Biometrik Dinamis*. Kunci fisik (access token) tidak berguna tanpa kehadiran fisik dan verifikasi biometrik langsung (DPoP Proof) dari pemilik sah saat kunci diputar di pintu brankas.
- **OPA Engine**: Seperti *Petugas Kepatuhan Independen* yang berdiri di depan brankas. Petugas tidak peduli seberapa mulus kunci Anda berputar; ia akan membuka buku aturan tebal dan memastikan: "*Apakah nasabah ini diizinkan menarik lebih dari Rp 100 juta di luar jam kerja cabang tanpa tanda tangan kuasa direksi?*"

#### Diagram Arsitektur Proteksi API & Egress SSRF

```
                                      KUBERNETES CLUSTER / CLOUD VPC
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  +--------------------+       mTLS        +-------------------------+                             |
|  |   API Gateway      | ----------------> |  Upstream Microservice  |                             |
|  |   (Envoy + OPA)    |                   |  (Order/Payment Engine) |                             |
|  +--------------------+                   +-------------------------+                             |
|            │                                           │                                          |
|            │ Validate Access                           │ Outbound HTTP/Webhook                    |
|            ▼                                           ▼                                          |
|    +---------------+                        +----------------------+                              |
|    | Redis Cluster |                        | Secure Egress Proxy  |                              |
|    | (Nonce & RLS) |                        | (Envoy / Smokescreen)|                              |
|    +---------------+                        +----------------------+                              |
|                                                        │                                          |
|                                         +--------------+--------------+                           |
|                                         │ Blokir Private IP           │ Resolusi DNS Terkontrol  |
|                                         │ (10.0.0.0/8, 169.254.169.254)                          |
|                                         ▼                             ▼                           |
|                                  [ BLOCKED/LOGGED ]         [ External Partner API ]              |
|                                  (Mitigasi SSRF API7)          (Contoh: Stripe/Twilio)            |
+---------------------------------------------------------------------------------------------------+
```

---

### 7. Practical Implementation Code (Standar Industri)

Implementasi di bawah menggunakan **Go (Golang)**: sebuah middleware API Gateway enterprise yang memverifikasi validitas **DPoP (RFC 9449)**, mengevaluasi otorisasi **OPA (Open Policy Agent)** untuk memitigasi **BOLA/BOPLA**, dan memvalidasi payload untuk menghentikan **Mass Assignment**.

#### Dependensi Go (`go.mod`)
```text
module enterprise-api-security

go 1.22

require (
	github.com/golang-jwt/jwt/v5 v5.2.1
	github.com/lestrrat-go/jwx/v2 v2.0.21
	github.com/open-policy-agent/opa v0.64.1
	github.com/redis/go-redis/v9 v9.5.1
)
```

#### File: `gateway/security_middleware.go`
```go
package gateway

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/lestrrat-go/jwx/v2/jwk"
	"github.com/open-policy-agent/opa/rego"
	"github.com/redis/go-redis/v9"
)

type SecurityMiddleware struct {
	RedisClient *redis.Client
	OpaQuery    rego.PreparedEvalQuery
}

// Inisialisasi Security Middleware dengan OPA Rego Engine
func NewSecurityMiddleware(redisAddr string, opaPolicy string) (*SecurityMiddleware, error) {
	rdb := redis.NewClient(&redis.Options{
		Addr: redisAddr,
	})

	ctx := context.Background()
	query, err := rego.New(
		rego.Query("data.authz.allow"),
		rego.Module("authz.rego", opaPolicy),
	).PrepareForEval(ctx)

	if err != nil {
		return nil, fmt.Errorf("gagal kompilasi OPA policy: %w", err)
	}

	return &SecurityMiddleware{
		RedisClient: rdb,
		OpaQuery:    query,
	}, nil
}

// Struct untuk memetakan Access Token Payload
type CustomClaims struct {
	UserID string            `json:"sub"`
	Role   string            `json:"role"`
	Cnf    map[string]string `json:"cnf"` // Menyimpan thumbprint 'jkt'
	jwt.RegisteredClaims
}

func (sm *SecurityMiddleware) EnforceZeroTrustAPI(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()

		// 1. Ekstraksi DPoP Proof & Access Token
		dpopHeader := r.Header.Get("DPoP")
		authHeader := r.Header.Get("Authorization")

		if dpopHeader == "" || !strings.HasPrefix(authHeader, "DPoP ") {
			http.Error(w, `{"error": "invalid_token_type", "message": "DPoP sender-constrained token diperlukan"}`, http.StatusUnauthorized)
			return
		}
		rawAccessToken := strings.TrimPrefix(authHeader, "DPoP ")

		// 2. Verifikasi DPoP Proof Token & Thumbprint
		jwkPublicKey, err := sm.validateDPoPProof(ctx, dpopHeader, r.Method, r.URL.String())
		if err != nil {
			http.Error(w, fmt.Sprintf(`{"error": "invalid_dpop_proof", "detail": "%s"}`, err.Error()), http.StatusUnauthorized)
			return
		}

		// 3. Verifikasi Access Token dan Cocokkan dengan JWK DPoP Thumbprint (jkt binding)
		claims, err := sm.validateAccessToken(rawAccessToken, jwkPublicKey)
		if err != nil {
			http.Error(w, fmt.Sprintf(`{"error": "token_validation_failed", "detail": "%s"}`, err.Error()), http.StatusUnauthorized)
			return
		}

		// 4. Membaca & Menyalin Request Body untuk Evaluasi OPA (Anti Mass-Assignment & BOLA)
		var bodyBytes []byte
		if r.Body != nil {
			bodyBytes, _ = io.ReadAll(r.Body)
			r.Body = io.NopCloser(bytes.NewBuffer(bodyBytes)) // restore stream
		}

		var parsedBody map[string]interface{}
		if len(bodyBytes) > 0 {
			if err := json.Unmarshal(bodyBytes, &parsedBody); err != nil {
				http.Error(w, `{"error": "malformed_json"}`, http.StatusBadRequest)
				return
			}
		}

		// 5. OPA Context Evaluation (PDP)
		input := map[string]interface{}{
			"user": map[string]interface{}{
				"id":   claims.UserID,
				"role": claims.Role,
			},
			"request": map[string]interface{}{
				"method": r.Method,
				"path":   r.URL.Path,
				"params": r.URL.Query(),
				"body":   parsedBody,
			},
		}

		results, err := sm.OpaQuery.Eval(ctx, rego.EvalInput(input))
		if err != nil || len(results) == 0 || !results[0].Bindings["data.authz.allow"].(bool) {
			http.Error(w, `{"error": "access_denied", "message": "Kebijakan otorisasi menolak aksi ini (BOLA/BOPLA protection)"}`, http.StatusForbidden)
			return
		}

		// Lolos verifikasi, lanjutkan ke next handler
		next.ServeHTTP(w, r)
	})
}

// Internal Validasi DPoP Proof (RFC 9449)
func (sm *SecurityMiddleware) validateDPoPProof(ctx context.Context, dpopToken string, expectedMethod string, expectedURI string) (jwk.Key, error) {
	// Parse Token header untuk mendapatkan Ephemeral JWK
	tok, err := jwt.Parse(dpopToken, func(token *jwt.Token) (interface{}, error) {
		jwkRaw, exists := token.Header["jwk"]
		if !exists {
			return nil, errors.New("header 'jwk' tidak ditemukan pada DPoP token")
		}
		jsonBytes, _ := json.Marshal(jwkRaw)
		key, err := jwk.ParseKey(jsonBytes)
		if err != nil {
			return nil, err
		}
		var rawKey interface{}
		if err := key.Raw(&rawKey); err != nil {
			return nil, err
		}
		return rawKey, nil
	})

	if err != nil || !tok.Valid {
		return nil, fmt.Errorf("signature DPoP tidak valid: %w", err)
	}

	claims, ok := tok.Claims.(jwt.MapClaims)
	if !ok {
		return nil, errors.New("klaim DPoP tidak valid")
	}

	// a. Validasi HTTP Method ('htm') dan URI ('htu')
	if claims["htm"] != expectedMethod {
		return nil, fmt.Errorf("mismatch klaim 'htm': expected %s, got %v", expectedMethod, claims["htm"])
	}
	if !strings.HasPrefix(expectedURI, claims["htu"].(string)) {
		return nil, fmt.Errorf("mismatch klaim 'htu': URI tidak cocok")
	}

	// b. Replay Attack Prevention via Unique JTI in Redis
	jti, ok := claims["jti"].(string)
	if !ok || jti == "" {
		return nil, errors.New("klaim 'jti' hilang")
	}

	redisKey := fmt.Sprintf("dpop:jti:%s", jti)
	setSuccess, err := sm.RedisClient.SetNX(ctx, redisKey, "1", 5*time.Minute).Result()
	if err != nil || !setSuccess {
		return nil, errors.New("dpop proof replay detected: JTI sudah pernah digunakan")
	}

	// c. Ambil kembali JWK object untuk verifikasi thumbprint Access Token
	jwkRaw := tok.Header["jwk"]
	jsonBytes, _ := json.Marshal(jwkRaw)
	return jwk.ParseKey(jsonBytes)
}

// Internal Validasi Access Token terhadap JKT Confirmation Claim
func (sm *SecurityMiddleware) validateAccessToken(rawToken string, clientKey jwk.Key) (*CustomClaims, error) {
	// Contoh: Static secret/Public key perusahaan (pada riil: ambil dari JWKS via cache)
	jwtSecret := []byte("ENTERPRISE_INTERNAL_SIGNING_KEY_CHANGE_IN_PROD")

	claims := &CustomClaims{}
	token, err := jwt.ParseWithClaims(rawToken, claims, func(token *jwt.Token) (interface{}, error) {
		return jwtSecret, nil
	})

	if err != nil || !token.Valid {
		return nil, errors.New("access token signature invalid / expired")
	}

	// Hitung SHA256 Thumbprint dari Public Key klien (JKT)
	thumbprint, err := clientKey.Thumbprint(sha256.New())
	if err != nil {
		return nil, errors.New("gagal menghitung thumbprint JWK")
	}
	encodedThumbprint := base64.RawURLEncoding.EncodeToString(thumbprint)

	// Validasi kecocokan dengan klaim cnf.jkt di Access Token
	cnfJKT, exists := claims.Cnf["jkt"]
	if !exists || cnfJKT != encodedThumbprint {
		return nil, errors.New("sender-constraint violation: token ini tidak terikat pada client private key saat ini")
	}

	return claims, nil
}
```

#### Kebijakan Deklaratif OPA Rego (`authz.rego`)
Kebijakan ini mengamankan BOLA (mengecek `account_id` yang diakses sesuai kepemilikan JWT `sub`) dan BOPLA / Mass Assignment (melarang mutasi field terlarang seperti `is_admin`, `balance`, atau `kyc_status`).

```rego
package authz

default allow = false

# Definisi field terlarang yang tidak boleh diubah oleh non-admin (Anti-BOPLA / Mass Assignment)
blacklisted_fields := ["role", "is_admin", "balance", "kyc_status", "internal_status"]

# Rule 1: Allow jika User adalah Administrator
allow {
    input.user.role == "SYSTEM_ADMIN"
}

# Rule 2: Proteksi BOLA & BOPLA pada endpoint Update Data Akun Nasabah
allow {
    # Endpoint: PUT /v1/accounts/{accountId}
    input.request.method == "PUT"
    startswith(input.request.path, "/v1/accounts/")
    
    # Ekstraksi target account ID dari path
    path_segments := split(trim(input.request.path, "/"), "/")
    target_account_id := path_segments[2]
    
    # 1. BOLA Check: Pengguna HANYA boleh memodifikasi resource miliknya sendiri
    input.user.id == target_account_id
    
    # 2. BOPLA Check: Payload TIDAK BOLEH memuat properti sensitif (Mass Assignment Guard)
    payload_keys := {key | input.request.body[key]}
    illegal_keys := payload_keys & set(blacklisted_fields)
    count(illegal_keys) == 0
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Kasus: Insiden Penetrasi API Institusi Perbankan Digital FinTech (2023)
- **Topologi**: FinTech melayani 4 juta transaksi harian via microservices di AWS EKS, diamankan oleh Kong API Gateway konvensional dengan Bearer JWT RS256.
- **Vektor Serangan**:
  1. *Exfiltration via SSRF*: Penyerang menemukan blind SSRF pada modul *Document Verification Webhook*. Penyerang mengekstraksi log internal dari Elasticsearch yang memuat ribuan `Authorization: Bearer eyJhbGci...` pengguna aktif.
  2. *BOLA Exploitation*: Penyerang memutar Bearer token tersebut untuk mengeksekusi request `PATCH /api/v2/wallets/{wallet_id}`. Gateway hanya mengecek validitas tanda tangan JWT (apakah token valid), tanpa memverifikasi relasi kepemilikan antara `wallet_id` dan `sub` di token.
  3. *Mass Assignment*: Melalui manipulasi payload JSON `{"balance": 100000000, "is_verified": true}`, penyerang berhasil menaikkan limit saldo secara artifisial karena struct unmarshaling backend meng-overwrite semua field basis data.
- **Dampak Finansial & Regulasi**: Potensi kerugian Rp 14,2 Miliar, ancaman denda regulasi privasi data, dan pembekuan lisensi pembayaran selama 30 hari.
- **Solusi Remediasi Produksi**:
  1. Migrasi dari Bearer Token ke **RFC 9449 (DPoP)** dalam 72 jam: Akses token yang diekstraksi dari Elasticsearch menjadi *tidak berguna* bagi penyerang karena penyerang tidak memiliki *ephemeral private key* yang tersimpan di Secure Enclave perangkat seluler nasabah.
  2. Penerapan **Envoy WASM + OPA ABAC**: Seluruh mutasi URI diverifikasi di gateway. Hubungan antara ID URL dan ID Subjek ditolak langsung di edge bila terjadi diskrepansi.
  3. Strict Deserialization Schema: Penggunaan Protocol Buffers (gRPC) untuk internal services dan pemetaan JSON DTO kaku tanpa generic dynamic reflection di layer HTTP REST.

---

### 9. Trade-offs: Architectural Decision Analysis

| Keputusan Arsitektur | Keuntungan | Biaya / Trade-off | Mitigasi Trade-off |
| :--- | :--- | :--- | :--- |
| **DPoP (RFC 9449)** | Menghilangkan risiko pencurian token (Token Theft / Exfiltration) secara total pada transport layer. | Komputasi tinggi: Verifikasi signature asymmetric (ECDSA) 2x lipat per request (DPoP JWT + Access Token). | Gunakan kurva eliptik modern (Ed25519 atau ECDSA P-256) bukan RSA-4096; delegasikan parsing ke Gateway level C++/Rust (Envoy). |
| **Centralized ABAC via OPA (Decoupled Engine)** | Audit trail satu pintu; pembaruan regulasi keamanan tanpa perlu re-deploy / re-compile microservices bisnis. | Network hop latency: Menambah latency ~2-5ms bila OPA dipanggil secara remote via HTTP/gRPC. | Jalankan OPA sebagai **Local Daemon / Sidecar** di localhost pod (komunikasi via UDS - Unix Domain Sockets); aktifkan compiled Wasm rules. |
| **Distributed L7 Rate Limiting (Redis Cell/Sliding Window)** | Proteksi presisi terhadap serangan Slowloris, Distributed Scraping, dan credential stuffing di layer 7. | Ketergantungan kritis pada cluster in-memory (Redis); jika Redis down/partisi jaringan, API bisa gagal bayar (*fail-closed* vs *fail-open*). | Implementasikan *circuit breaker*: Jika Redis RTT > 15ms, fallback sementara ke Local In-Memory Token Bucket dengan log alarm kritis. |
| **Strict Schema Engine (Reject Unknown Fields)** | Mencegah Mass Assignment / Parameter Tampering / BOPLA secara absolut. | *Backward compatibility* rentan rusak jika klien versi lama mengirim field usang, atau klien versi baru diperbarui lebih dulu dibanding gateway. | Semantic API versioning ketat (`/v1`, `/v2`) dan pipeline validasi kontrak otomatis menggunakan Spectral OpenAPI Linter pada CI/CD. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. JWKS (JSON Web Key Set) Cache Invalidation & SSRF Hijacking
- **Kesalahan**: API Gateway mengambil file JWKS dari header JWT `jku` (JWK Set URL) yang dikirim oleh client tanpa *domain allowlisting*.
- **Dampak**: Critical RCE/Auth Bypass. Penyerang mengarahkan `jku` ke server miliknya (`https://attacker.com/.well-known/jwks.json`), menandatangani token dengan key-nya sendiri, dan Gateway memvalidasinya sebagai valid.
- **Solusi**: Matikan pembacaan header `jku` dinamis. Muat public key secara eksklusif dari OIDC Identity Provider internal yang di-hardcode dengan fallback *stale-while-revalidate caching*.

#### 2. DPoP Replay Attacks Window Leak
- **Kesalahan**: Gateway hanya memvalidasi signature DPoP tanpa menyimpan status unik identitas `jti` (JWT ID), atau menyimpannya dengan TTL yang terlalu lama (> 1 jam).
- **Dampak**: Jika penyerang menyadap request dalam window aktif yang sama via compromised proxy, penyerang dapat menembakkan ulang (*replay*) request tersebut berkali-kali.
- **Solusi**: Enforce TTL DPoP `iat` (Issued At) maksimal 60-120 detik, dan simpan `jti` di Redis dengan key expiry yang identik. Jika `jti` duplikat masuk, lempar HTTP 401 Unauthorized secara permanen.

#### 3. Regex Catastrophic Backtracking (ReDoS) pada WAF Rules
- **Kesalahan**: Menulis *custom regex* evaluasi body payload di middleware menggunakan pattern non-deterministik: `^([a-zA-Z0-9]+)*$`.
- **Dampak**: Denial of Service massal (CPU Spike 100%) hanya dengan mengirim string acak panjang: `aaaaaaaaaaaaaaaaaaaaaaaaaaaa!`.
- **Solusi**: Gunakan regex engine berbasis Linear Time (seperti Google RE2 di Go atau Envoy) yang menjamin waktu eksekusi $O(n)$ dan menolak sintaks backtracking seperti backreferences atau lookahead kompleks.

---

### 11. Best Practices (Production Checklist)

Gunakan daftar periksa ini sebelum merilis API ke lingkungan Production:

- [ ] **Transport Layer**:
  - [ ] Enforce TLS 1.3 secara eksklusif (nonaktifkan TLS 1.0, 1.1, dan seluruh cipher CBC/RC4 pada TLS 1.2).
  - [ ] Terapkan HTTP Strict Transport Security (HSTS) dengan `max-age=63072000; includeSubDomains; preload`.
- [ ] **Identity & Token Handling**:
  - [ ] Nonaktifkan algoritma `none` dan tolak secara eksplisit *algorithm switching* (misal: RS256 diubah menjadi HS256).
  - [ ] Terapkan DPoP (RFC 9449) untuk seluruh aplikasi web modern (SPA) dan mobile clients.
  - [ ] Terapkan sertifikat mTLS (RFC 8705) untuk komunikasi B2B (Server-to-Server).
- [ ] **Endpoint Authorization (Anti-BOLA/BOPLA)**:
  - [ ] Konfigurasi OPA/ABAC sidecar untuk memvalidasi kepemilikan data pada setiap method `GET`, `PUT`, `PATCH`, `DELETE`.
  - [ ] Konfigurasi serializer JSON: `disallowUnknownFields: true` atau AST parsing guard untuk menolak parameter asing.
- [ ] **Egress & Ingress Boundary**:
  - [ ] Terapkan *Smokescreen* / Hardened Forward Egress Proxy untuk setiap modul pemanggilan webhook outbound (Anti-SSRF).
  - [ ] Integrasikan Envoy Rate Limiting Service dengan JA4 TLS fingerprinting di Edge.
- [ ] **Defensive Headers**:
  - [ ] `Content-Security-Policy: default-src 'none'; frame-ancestors 'none';` (khusus API service).
  - [ ] `X-Content-Type-Options: nosniff`.
  - [ ] `Cache-Control: no-store, no-cache, must-revalidate, private`.

---

### 12. Hands-on Practice: Membangun Production-Grade API Hardening Layer

Simpan seluruh file praktikum ini di direktori: `hands-on/m02/`

#### Skenario Praktikum:
Anda akan mengonfigurasi dan menjalankan verifikasi DPoP sender-constrained token dan policy ABAC OPA lokal untuk menggagalkan upaya pembajakan BOLA & Mass Assignment.

#### Langkah 1: Siapkan Struktur Direktori
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
go mod init enterprise-api-defense
```

#### Langkah 2: Buat Kebijakan Rego (`policy.rego`)
Buat file `policy.rego`:
```rego
package authz

default allow = false

# Dilarang mutasi saldo atau status verifikasi
forbidden_keys := {"account_balance", "is_admin", "status"}

allow {
    input.method == "POST"
    input.path == "/v1/transfer"
    
    # BOLA Guard: Pengirim transfer HARUS sama dengan ID pemilik token
    input.token_user_id == input.body.sender_account_id
    
    # BOPLA Guard: Memastikan tidak ada field ilegal yang diinjeksi
    body_keys := {k | input.body[k]}
    intersection := body_keys & forbidden_keys
    count(intersection) == 0
}
```

#### Langkah 3: Buat Program Evaluator & Pengujian (`main.go`)
Buat file `main.go`:
```go
package main

import (
	"context"
	"fmt"
	"log"

	"github.com/open-policy-agent/opa/rego"
)

func evaluateRequest(ctx context.Context, query rego.PreparedEvalQuery, tokenUID string, senderUID string, payload map[string]interface{}) bool {
	input := map[string]interface{}{
		"method":        "POST",
		"path":          "/v1/transfer",
		"token_user_id": tokenUID,
		"body":          payload,
	}

	results, err := query.Eval(ctx, rego.EvalInput(input))
	if err != nil || len(results) == 0 {
		return false
	}

	allowed, ok := results[0].Bindings["data.authz.allow"].(bool)
	return ok && allowed
}

func main() {
	ctx := context.Background()

	// 1. Compile Rego File
	query, err := rego.New(
		rego.Query("data.authz.allow"),
		rego.Load([]string{"policy.rego"}, nil),
	).PrepareForEval(ctx)
	if err != nil {
		log.Fatalf("Gagal inisialisasi OPA: %v", err)
	}

	fmt.Println("=== RUNNING API SECURITY EVALUATION SCENARIOS ===")

	// Skenario A: Normal Request (Valid BOLA & Valid Payload)
	payloadA := map[string]interface{}{
		"sender_account_id": "user-123",
		"target_account_id": "user-999",
		"amount":            50000,
	}
	resA := evaluateRequest(ctx, query, "user-123", "user-123", payloadA)
	fmt.Printf("[Test 1] Transfer Normal (Expected: ALLOWED): %v\n", resA)

	// Skenario B: Serangan BOLA (Token user-123 mencoba transfer dari rekening user-456)
	payloadB := map[string]interface{}{
		"sender_account_id": "user-456", // ID Rekening Orang Lain
		"target_account_id": "user-999",
		"amount":            50000,
	}
	resB := evaluateRequest(ctx, query, "user-123", "user-456", payloadB)
	fmt.Printf("[Test 2] Serangan BOLA / IDOR (Expected: DENIED): %v\n", resB)

	// Skenario C: Serangan BOPLA / Mass Assignment (User mencoba injeksi saldo dan status admin)
	payloadC := map[string]interface{}{
		"sender_account_id": "user-123",
		"target_account_id": "user-999",
		"amount":            50000,
		"account_balance":   999999999, // Parameter terlarang
		"is_admin":          true,      // Parameter terlarang
	}
	resC := evaluateRequest(ctx, query, "user-123", "user-123", payloadC)
	fmt.Printf("[Test 3] Serangan Mass Assignment (Expected: DENIED): %v\n", resC)
}
```

#### Langkah 4: Jalankan dan Verifikasi
```bash
go get github.com/open-policy-agent/opa/rego
go run main.go
```
*Ekspektasi Output:*
```text
=== RUNNING API SECURITY EVALUATION SCENARIOS ===
[Test 1] Transfer Normal (Expected: ALLOWED): true
[Test 2] Serangan BOLA / IDOR (Expected: DENIED): false
[Test 3] Serangan Mass Assignment (Expected: DENIED): false
```

---

### 13. Exercise

#### Level Easy
Tuliskan konfigurasi HTTP Security Headers dalam bentuk format respons reverse proxy NGINX enterprise yang secara agresif menonaktifkan *MIME sniffing*, melarang situs dimasukkan ke dalam `<iframe>` pihak ketiga mana pun (*clickjacking mitigation*), dan menetapkan `Content-Security-Policy` API yang memblokir semua eksekusi resource non-JSON.

#### Level Medium
Sebuah endpoint REST menerima URL callback webhook dari nasabah: `POST /v1/webhooks` dengan body `{"url": "https://..."}`. Rancang fungsi validator di Go yang:
1. Memvalidasi format URL.
2. Menggunakan `net.LookupIP` untuk me-resolve alamat IP target.
3. Menolak registrasi URL jika IP target termasuk dalam blok IP Loopback, RFC 1918 (Private Network), atau IPv6 link-local addresses untuk memitigasi SSRF.

#### Level Hard
Rancang aturan OPA (Rego) lengkap yang mengevaluasi kebijakan otorisasi multi-tenant dengan parameter:
- Tenant A tidak boleh mengakses data Tenant B dalam kondisi apa pun.
- Pengguna dengan peran `BRANCH_MANAGER` hanya boleh melakukan persetujuan (approve) pinjaman (`POST /loans/{id}/approve`) jika atribut `loan_amount` $\le$ Rp 500.000.000 dan `office_id` pinjaman tersebut sama dengan `office_id` di klaim JWT pengguna.
- Pinjaman > Rp 500.000.000 hanya dapat di-approve oleh pengguna dengan peran `REGIONAL_DIRECTOR`.

---

### 14. Challenge (Studi Kasus Arsitektur Kompleks)

**Konteks Kasus**:
Sebuah perusahaan Core Banking memproses jutaan request API transfer dana per jam. Mereka menghadapi tantangan:
1. Penyerang menyewa botnet berbasis perumahan (*residential proxies*) dengan jutaan alamat IP unik yang memutar IP setiap 3 request, membuat *IP-based Rate Limiting* di AWS WAF tidak berguna.
2. Penyerang mengeksploitasi celah *Race Condition* (*Limit-Overrun / TOCTOU*) pada endpoint `POST /v1/promotions/redeem`, menarik cashback 100 kali dalam interval 2 milidetik sebelum database mengunci saldo balance.

**Tantangan Arsitektur**:
Rancang dokumen arsitektur dan diagram integrasi pertahanan menyeluruh (High-Level & Low-Level Design) tanpa menggunakan proteksi IP tunggal konvensional:
- Bagaimana Anda menggabungkan **JA4 TLS Fingerprinting**, **Proof-of-Work Challenge (mTLS/WebCrypto Proof)** di layer API Gateway, dan distributed state engine?
- Bagaimana Anda merancang mitigasi *Race Condition* di distributed gateway layer sebelum request mencapai database ACID backend, dengan toleransi overhead latensi gateway di bawah **8 milidetik** pada p99?

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic Concepts (5 Soal)
1. Apa kelemahan utama arsitektur keamanan *Bearer Token* (RFC 6750) dibanding *Sender-Constrained Token*?
2. Dalam mekanisme DPoP (RFC 9449), klaim `htm` dan `htu` berfungsi untuk mencegah serangan apa? Jelaskan mekanismenya.
3. Sebutkan perbedaan mendasar antara kerentanan OWASP API Security BOLA (Broken Object Level Authorization) dan BOPLA (Broken Object Property Level Authorization)!
4. Mengapa algoritma mitigasi Rate Limiting *Fixed Window Counter* rentan terhadap *Traffic Burst* pada batas jendela waktu (*window boundaries*)?
5. Mengapa resolusi DNS internal aplikasi yang tidak dikunci (*DNS unpinned*) dapat memicu celah SSRF via teknik *DNS Rebinding*?

#### B. Intermediate Scenarios (5 Soal)
6. Sebuah tim engineering memindahkan otorisasi dari aplikasi monolitik ke OPA sidecar. Namun latensi p95 API melonjak dari 15ms ke 120ms. Komponen arsitektural apa yang paling berpotensi menyebabkan *latency penalty* ini, dan bagaimana memperbaikinya?
7. Bagaimana penyerang dapat melewati (*bypass*) validasi DPoP jika gateway mengimplementasikan verifikasi tanda tangan JWK tetapi tidak memvalidasi klaim `jti`?
8. Anda menemukan log berikut di API Gateway: `POST /api/v1/users/45 HTTP/1.1` dengan body `{"id": 45, "email": "test@test.com", "role": "admin"}`. Status response: `200 OK`. Jika database mengubah kolom role user menjadi admin, pola kegagalan arsitektur apa yang terjadi di sini?
9. Apa perbedaan teknis implementasi mTLS RFC 8705 (`cnf.x5t#S256`) dengan DPoP RFC 9449 (`cnf.jkt`), dan dalam skenario apa mTLS lebih disukai dibanding DPoP?
10. Mengapa pemeriksaan WAF berbasis Regular Expression (Regex) sering kali tidak memadai untuk mendeteksi *Payload Deserialization Attacks* pada format JSON atau XML bertingkat (*nested*)?

#### C. Production Case Troubleshooting (3 Skenario Kasus)
11. **Skenario Kasus 1**: API Gateway Anda menerima lonjakan error `401 Unauthorized` sebesar 40% secara tiba-tiba dari pengguna sah mobile apps setelah pembaruan arsitektur ke DPoP. Sistem jam pada klien terdeteksi mengalami *clock drift* sebesar 3 hingga 5 menit dibanding NTP Server gateway. Konfigurasi apa di DPoP middleware yang harus disesuaikan secara presisi tanpa membuka celah replay attack?
12. **Skenario Kasus 2**: Sebuah microservice internal payment engine di-deploy di Kubernetes. Layanan ini tidak memiliki public IP dan hanya melayani request internal gRPC. Namun, penyerang yang berhasil masuk ke pod lain (melalui celah Remote Code Execution di container frontend) berhasil melakukan transfer dana liar dengan memalsukan header `X-User-ID: 1`. Kerentanan arsitektural apa yang ada di jaringan internal tersebut, dan bagaimana SPIFFE/SPIRE dan mTLS Service Mesh memperbaikinya?
13. **Skenario Kasus 3**: Tim Anda menggunakan Envoy Proxy yang menjalankan ModSecurity WASM Engine. Ketika traffic Black Friday mencapai 50.000 RPS, memori Envoy pod mengalami *OOMKilled* (Out-Of-Memory) secara berkala. Analisis heap dump menunjukkan bahwa akumulasi buffer terjadi pada parsing request body berukuran besar. Konfigurasi mitigasi darurat apa yang harus diterapkan di level Envoy route dan filter buffer sebelum payload mencapai WASM engine?

---

### 16. Summary

1. **Sender-Constrained Tokens Menjadi Standar Baru**: Keamanan token API enterprise telah beralih dari Bearer Tokens yang pasif menuju **DPoP (RFC 9449)** dan **mTLS (RFC 8705)**, di mana token diikat secara kriptografis ke pasangan kunci publik-privat klien untuk menihilkan dampak pencurian token.
2. **Dekoupling Kebijakan Keamanan dengan ABAC & OPA**: RBAC tradisional tidak mampu menangani ancaman BOLA/BOPLA. Pemisahan *Policy Decision Point* (PDP) menggunakan mesin berbasis Rego (OPA) menjamin evaluasi dinamis terhadap identitas subjek, relasi kepemilikan data, dan restriksi payload mutasi secara terpusat.
3. **Defense-in-Depth pada Layer Egress dan Ingress**: Keamanan API tidak hanya memvalidasi traffic yang masuk (Ingress rate-limiting, WAF WASM, JSON schema guard), tetapi juga mengisolasi traffic keluar (Egress proxy) secara ketat guna meniadakan eksploitasi Blind SSRF terhadap infrastruktur cloud internal.