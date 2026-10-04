## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** API-DES-0601
* **Nama Modul:** Enterprise API Security, Identity, & Governance: OAuth 2.1, OIDC, FAPI, mTLS, Token Binding DPoP, Authorization Policy OPA Rego & ABAC
* **Kategori:** 06-Architecture-and-System-Design
* **Jalur Kurikulum:** API Design & Enterprise Architecture
* **Target Audiens:** Principal Software Engineer, Lead API Architect, Enterprise Security Engineer, Staff Platform Engineer
* **Prasyarat Teknis:**
  * Pemahaman mendalam tentang HTTP/1.1, HTTP/2, dan TLS 1.3 handshake.
  * Pengalaman dengan arsitektur berbasis token (RFC 7519 JSON Web Token / JWT, RFC 7515 JWS).
  * Penguasaan dasar OAuth 2.0 framework (RFC 6749, RFC 6750).
  * Pemahaman fundamental distributed systems dan arsitektur API Gateway (Reverse Proxy, PEP/PDP).
* **Estimasi Durasi:** 4 jam teori mendalam + 6 jam laboratorium teknis hands-on.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:

1. **Menganalisis dan Memitigasi Celah Arsitektural OAuth 2.0 Warisan:** Mengidentifikasi kelemahan mendasar dari *Implicit Grant* dan *Resource Owner Password Credentials* (ROPC), lalu merancang migrasi arsitektur menuju konsolidasi OAuth 2.1 dengan *Proof Key for Code Exchange* (PKCE) dan validasi *exact redirect URI*.
2. **Mengimplementasikan Financial-grade API (FAPI 1.0/2.0) Profile:** Merancang arsitektur interaksi API tingkat perbankan/finansial dengan menerapkan *Pushed Authorization Requests* (PAR - RFC 9126), *JWT Secured Authorization Response Mode* (JARM - RFC 9101), dan *mTLS Client Authentication* (RFC 8705).
3. **Mencegah Pencurian dan Replay Token dengan Token Binding (mTLS & DPoP):** Mengeliminasi risiko *bearer token theft* melalui implementasi *Demonstrating Proof-of-Possession at the Application Layer* (DPoP - RFC 9449) pada layer aplikasi dan *Certificate-Bound Access Tokens* pada layer transport.
4. **Membangun Desentralisasi Otorisasi Fine-Grained dengan ABAC dan OPA Rego:** Memisahkan *Policy Enforcement Point* (PEP) dan *Policy Decision Point* (PDP) menggunakan Open Policy Agent (OPA) berbasis bahasa deklaratif Rego untuk menegakkan kontrol akses multi-atribut kontekstual (subjek, resource, aksi, lingkungan).
5. **Menegakkan Governance API Zero-Trust:** Mengintegrasikan siklus hidup *identity federation* (OIDC), rotasi kunci asimetris (*JWKS lifecycle management*), dan verifikasi kriptografis terdistribusi tanpa memperkenalkan *single point of failure* atau latensi berlebih.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                              [ENTERPRISE API SECURITY GOVERNANCE]
                                                |
         +--------------------------------------+--------------------------------------+
         |                                                                             |
[IDENTITY & PROTOCOL LAYER]                                                  [AUTHORIZATION LAYER]
         |                                                                             |
         +--> OAuth 2.1 Consolidated Spec                                              +--> Decoupled Access Control
         |    |-- Mandated PKCE for all clients                                        |    |-- PEP (API Gateway/Service Mesh)
         |    |-- Deprecated Implicit & ROPC grants                                    |    +-- PDP (Open Policy Agent - OPA)
         |    +-- Strict Redirect URI match                                            |
         |                                                                             +--> ABAC Paradigm
         +--> OpenID Connect (OIDC) Core 1.0                                           |    |-- Subject Attributes
         |    |-- ID Token vs Access Token separation                                  |    |-- Resource Attributes
         |    +-- Discovery (.well-known) & UserInfo                                   |    |-- Action Attributes
         |                                                                             |    +-- Contextual/Env Attributes (IP, Time)
         +--> FAPI (Financial-grade API) Baseline & Advanced                           |
         |    |-- Pushed Authorization Requests (PAR)                                  +--> OPA Rego Policy Engine
         |    |-- JWT Secured Authorization Response (JARM)                                 |-- Declarative Evaluation
         |    +-- Cryptographic Non-Repudiation                                             +-- Sidecar/Embedded Execution Cache
         |
[TOKEN BINDING & TRANSPORT DEFENSE]
         |
         +--> Mutual TLS (mTLS - RFC 8705)
         |    |-- Transport-layer Client Identity
         |    +-- Sender-Constrained Tokens via Certificate SHA-256 Thumbprint (x5t#S256)
         |
         +--> DPoP (RFC 9449)
              |-- Application-layer Proof of Possession
              |-- Asymmetric Key Pair generated at Client
              |-- DPoP Proof JWT with htm, htu, jti, and ath (Access Token Hash)
              +-- Replay Attack Prevention via In-Memory Ephemeral Nonce
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sistem enterprise modern tidak lagi beroperasi dalam perimeter jaringan tertutup (intranet). Model keamanan berbasis batas jaringan (*perimeter security*) telah sepenuhnya usang dan digantikan oleh paradigma **Zero Trust Architecture** (NIST SP 800-207): *Never Trust, Always Verify*.

### Dampak Kritis Tanpa Arsitektur Keamanan Modern

1. **Bearer Token Hijacking (The "Cash Currency" Problem):**
   Pada implementasi OAuth 2.0 klasik, *access token* bertindak layaknya uang tunai (*bearer*). Siapa pun yang mencuri token tersebut—baik melalui *log leakage*, *man-in-the-middle* (MitM) interception, memori *frontend*, atau *cross-site scripting* (XSS)—dapat menggunakannya ke API backend secara anonim tanpa bukti identitas kepemilikan.
2. **Keterbatasan RBAC (Role Explosion):**
   *Role-Based Access Control* (RBAC) konvensional gagal melayani model bisnis kompleks. Menugaskan peran seperti `REGIONAL_MANAGER_WEST_READ_ONLY` menciptakan ledakan variasi *role* (*role explosion*) yang tidak dapat dikelola (*unmaintainable*). ABAC (*Attribute-Based Access Control*) mengatasi hal ini dengan mengevaluasi kebijakan dinamis seperti: *"Apakah pengguna berada di departemen X, mengakses data klasifikasi Y, selama jam kerja, dari subnet Z?"*.
3. **Kopling Logika Bisnis dan Kebijakan Keamanan (Hardcoded Auth):**
   Ketika aturan otorisasi ditulis secara *hardcoded* di dalam kode aplikasi backend (`if (user.role == 'admin' && resource.owner == user.id)`), setiap perubahan kepatuhan regulasi mengharuskan siklus *re-build*, *re-test*, dan *re-deploy*. Ini melanggar prinsip *separation of concerns*.
4. **Persyaratan Kepatuhan Regulasi Finansial (Open Banking / FAPI):**
   Sektor perbankan, *fintech*, dan data kesehatan wajib mematuhi standar ketat seperti Open Banking UK, PSD2 RTS (Uni Eropa), dan FAPI (OpenID Foundation). Arsitektur API harus menyediakan *tamper-proof auditability*, *non-repudiation*, dan proteksi terhadap serangan pembajakan otorisasi di level *browser/user-agent*.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. OAuth 2.1
Konsolidasi resmi dari spesifikasi OAuth 2.0 inti beserta RFC-RFC perbaikannya:
* **Implicit Grant Dihapus:** Tidak ada lagi pengembalian token langsung via fragmen URL browser (`#access_token=...`), yang secara historis rentan kebocoran via riwayat browser dan *Referer header*.
* **Resource Owner Password Credentials (ROPC) Dihapus:** Klien dilarang meminta dan memproses langsung kredensial pengguna (username/password), mengeliminasi risiko *credential stuffing* pada aplikasi pihak ketiga.
* **PKCE Wajib untuk Seluruh Klien:** *Proof Key for Code Exchange* (RFC 7636) diwajibkan, tidak hanya untuk *public client* (aplikasi mobile/SPA), tetapi juga untuk *confidential client* (backend service) guna mencegah *Authorization Code Injection*.
* **Exact Redirect URI Matching:** Server otorisasi wajib mencocokkan URI pengalihan secara string-literal, melarang penggunaan *wildcard* yang rentan eksploitasi *open-redirector*.

### 2. OpenID Connect (OIDC) Core 1.0
Lapisan identitas terstandarisasi di atas OAuth 2.0/2.1. OAuth adalah protokol *otorisasi* ("apa yang boleh Anda akses"), sedangkan OIDC menyediakan *autentikasi* ("siapa Anda"). OIDC memperkenalkan:
* **ID Token:** JWT bertanda tangan kriptografis yang memuat informasi subjek pengguna (`sub`, `iss`, `aud`, `auth_time`).
* **UserInfo Endpoint:** Endpoint terproteksi untuk mengambil atribut profil subjek secara dinamis.
* **Metadata Discovery:** Standardisasi path `.well-known/openid-configuration` untuk distribusi endpoint dan kunci publik (`jwks_uri`).

### 3. FAPI (Financial-grade API)
Spesifikasi profil keamanan tinggi dari OpenID Foundation:
* **PAR (Pushed Authorization Requests - RFC 9126):** Parameter otorisasi tidak dikirim melalui *query parameter* browser yang rentan log sniffing, melainkan di-push langsung oleh klien ke server via koneksi backchannel terautentikasi sebelum redirect.
* **JARM (JWT Secured Authorization Response Mode - RFC 9101):** Respons dari Authorization Endpoint dienkapsulasi dan ditandatangani dalam bentuk JWT untuk menjamin integritas data dan mencegah manipulasi parameter respons (`code`, `state`).

### 4. Token Binding: mTLS vs DPoP
Mekanisme pengikatan token (*sender-constraining*) sehingga token hanya valid jika dikirim oleh pemegang kunci kriptografis yang sah:
* **Mutual TLS (RFC 8705):** Pengikatan token pada lapisan transport (Layer 4/TLS). Sertifikat X.509 klien diverifikasi saat TLS handshake; hash sertifikat klien (`x5t#S256`) ditanamkan ke dalam claim `cnf` (confirmation) di access token.
* **DPoP (RFC 9449):** Pengikatan token pada lapisan aplikasi (Layer 7/HTTP). Klien membuat *key-pair* asimetris publik/privat (biasanya ES256). Setiap pemanggilan API menyertakan header `DPoP` berupa JWT yang ditandatangani oleh *private key* klien, membuktikan kepemilikan kunci tersebut saat mengakses *protected resource*.

### 5. ABAC & Open Policy Agent (OPA)
* **ABAC (Attribute-Based Access Control):** Model otorisasi yang mengevaluasi hak akses berdasarkan kombinasi atribut subjek, resource, tindakan, dan konteks lingkungan saat *runtime*.
* **OPA (Open Policy Agent):** Mesin kebijakan open-source (*general-purpose policy engine*) yang mendeklarasikan kebijakan sebagai kode (*Policy as Code*) menggunakan bahasa deklaratif **Rego**. OPA memisahkan keputusan kebijakan (*PDP*) dari penegakan kebijakan (*PEP*).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

Berikut alur kerja end-to-end arsitektur keamanan API enterprise:

```
[Client Application]        [Authorization Server]        [API Gateway (PEP)]        [Policy Engine (OPA)]      [Upstream Microservice]
        |                             |                            |                           |                          |
        | 1. POST /par (Push params)   |                            |                           |                          |
        |---------------------------->|                            |                           |                          |
        |    request_uri return       |                            |                           |                          |
        |<----------------------------|                            |                           |                          |
        |                             |                            |                           |                          |
        | 2. GET /authorize?uri=...   |                            |                           |                          |
        |    (User logs in via IDP)   |                            |                           |                          |
        |---------------------------->|                            |                           |                          |
        | 3. Auth Code + JARM JWT     |                            |                           |                          |
        |<----------------------------|                            |                           |                          |
        |                             |                            |                           |                          |
        | 4. POST /token (Code + PKCE |                            |                           |                          |
        |    verifier + DPoP Proof)   |                            |                           |                          |
        |---------------------------->|                            |                           |                          |
        | 5. Sender-Constrained Token |                            |                           |                          |
        |    (DPoP bound via cnf.jkt) |                            |                           |                          |
        |<----------------------------|                            |                           |                          |
        |                                                          |                           |                          |
        | 6. HTTP Request + Bearer DPoP-Bound Token + DPoP Proof   |                           |                          |
        |--------------------------------------------------------->|                           |                          |
        |                                                          | 7. Verifikasi DPoP Proof  |                          |
        |                                                          |    & Validasi JWT Token   |                          |
        |                                                          |    (Signature & Expiry)   |                          |
        |                                                          |                           |                          |
        |                                                          | 8. Query PDP Evaluation   |                          |
        |                                                          |    POST /v1/data/authz    |                          |
        |                                                          |-------------------------->|                          |
        |                                                          |                           | 9. Evaluasi Rego Rule    |
        |                                                          |                           |    (Context, User Roles, |
        |                                                          |                           |     Resource Metadata)   |
        |                                                          | 10. {"allow": true}       |                          |
        |                                                          |<--------------------------|                          |
        |                                                          |                                                      |
        |                                                          | 11. Forward Request (Sanitized Context)             |
        |                                                          |----------------------------------------------------->|
        |                                                          | 12. Response Data                                    |
        |                                                          |<-----------------------------------------------------|
        | 13. HTTP Response                                        |                                                      |
        |<---------------------------------------------------------|                                                      |
```

### Langkah-Langkah Operasional Inti:

1. **Pushed Authorization Request (PAR):** Klien mengirimkan parameter otorisasi (scope, PKCE code challenge, redirect URI) secara langsung ke Authorization Server melalui HTTP POST terautentikasi. Klien menerima `request_uri`.
2. **User Authorization & JARM:** Browser diarahkan ke URL `/authorize?request_uri=urn:...`. Setelah pengguna menyetujui, Authorization Server mengembalikan respon terenkapsulasi JWT (JARM) ke redirect URI yang memuat `authorization_code`.
3. **Pertukaran Token DPoP:** Klien menukar kode otorisasi pada endpoint `/token`. Bersamaan dengan itu, klien membuat pasangan kunci ECDSA (P-256), membuat tanda tangan JWT (DPoP Proof), dan menyertakannya di header `DPoP`.
4. **Penerbitan Token Terikat:** Server otorisasi menerbitkan Access Token yang memuat claim konfirmasi:
   ```json
   "cnf": {
     "jkt": "0ZcOCORZTXDE...sha256-thumbprint-of-client-public-key..."
   }
   ```
5. **Pemanggilan API Gateway (PEP):** Klien memanggil resource API dengan menyertakan:
   * Header `Authorization: DPoP <access_token>`
   * Header `DPoP: <dpop_proof_jwt>` (yang memuat method HTTP, target URI, timestamp, jti, dan tanda tangan kunci privat klien).
6. **Verifikasi Kriptografis pada PEP:** API Gateway memverifikasi integritas signature JWT access token via JWKS. Gateway juga memverifikasi bahwa kunci publik pada header DPoP proof menghasilkan thumbprint SHA-256 yang cocok dengan claim `cnf.jkt` pada access token, serta memvalidasi kesesuaian nilai method (`htm`) dan target URI (`htu`).
7. **Delegasi Otorisasi ke OPA (PDP):** Gateway mengekstrak data identitas (dari token), metadata resource (dari URL dan database internal gateway), dan konteks lingkungan (IP asal, waktu akses), lalu mengirimkan *payload input* JSON ke OPA engine.
8. **Eksekusi Aturan ABAC:** Mesin Rego pada OPA mengevaluasi serangkaian logika multi-kondisi. Jika seluruh kriteria terpenuhi, OPA mengembalikan `{"allow": true}`.
9. **Dispatch ke Upstream:** API Gateway meneruskan request ke microservice target.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Komparasi Pola Token Binding: mTLS vs DPoP

```
+---------------------------------------------------------------------------------------------------+
| 1. mTLS TOKEN BINDING (RFC 8705) - LAYER 4 ENFORCEMENT                                            |
+---------------------------------------------------------------------------------------------------+
|  [Client]                                              [API Gateway (Terminates TLS)]            |
|     |                                                                |                            |
|     +===== TLS 1.3 Handshake (Client X.509 Certificate Sent) =======>|                            |
|     |      (Gateway extracts SHA-256 fingerprint: cert_fingerprint)  |                            |
|     |                                                                |                            |
|     |-- HTTP POST /api/transfer ------------------------------------>|                            |
|     |   Authorization: Bearer <Token>                                | Validasi:                  |
|     |                                                                | 1. Verify Token Signature  |
|     |                                                                | 2. Token cnf['x5t#S256']   |
|     |                                                                |    == cert_fingerprint     |
|     |                                                                | Jika tidak cocok -> 401    |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
| 2. DPoP TOKEN BINDING (RFC 9449) - LAYER 7 ENFORCEMENT                                            |
+---------------------------------------------------------------------------------------------------+
|  [Client]                                              [API Gateway (Any TLS Proxy Friendly)]     |
|     |                                                                |                            |
|     |  * Local Client: Generate Ephemeral Keypair (Priv/Pub)         |                            |
|     |  * Sign Proof JWT using PrivKey:                               |                            |
|     |    { "typ": "dpop+jwt", "alg": "ES256", "jwk": {Pub} }         |                            |
|     |    { "jti": "uuid", "htm": "POST", "htu": "https://api/..." }  |                            |
|     |                                                                |                            |
|     |-- HTTP POST https://api/... ---------------------------------->|                            |
|     |   Authorization: DPoP <Token>                                  | Validasi:                  |
|     |   DPoP: eyJhbGciOiJ... (DPoP Proof)                            | 1. Verify DPoP Signature   |
|     |                                                                |    menggunakan header.jwk  |
|     |                                                                | 2. SHA-256(header.jwk)    |
|     |                                                                |    == Token cnf['jkt']     |
|     |                                                                | 3. Proof.htm == 'POST'     |
|     |                                                                | 4. Proof.htu == target URL |
|     |                                                                | 5. Proof.jti belum dipakai |
+---------------------------------------------------------------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah struktur representasi nyata dari **DPoP Proof JWT** dan **Access Token Binding Claim**:

### 1. Header DPoP Proof JWT
```json
{
  "typ": "dpop+jwt",
  "alg": "ES256",
  "jwk": {
    "kty": "EC",
    "crv": "P-256",
    "x": "l8hggIj-UpEuFIjhCUvBD-JQTWBI5asuh2i6YPbhk2s",
    "y": "AbeX_AuhPBQG5Do90iUguLKzNOhTHP5CQY68V3Sad90"
  }
}
```

### 2. Payload DPoP Proof JWT
```json
{
  "jti": "c20ad761-41f2-45e0-b6c8-500b5220c3a2",
  "htm": "POST",
  "htu": "https://api.enterprise.com/v1/payments",
  "iat": 1711929600,
  "ath": "fUHyO2r2Z3DZ5320-Crown3F99nEYbv1mD8Uz2Elw22"
}
```
* `jti`: Pengidentifikasi unik untuk mencegah replay attack.
* `htm`: HTTP Method (POST).
* `htu`: HTTP URI tanpa query parameter dan fragment.
* `ath`: Base64URL-encoded SHA-256 hash dari *Access Token* yang dikirim bersamaan.

### 3. Payload Access Token (DPoP-Bound)
```json
{
  "iss": "https://identity.enterprise.com",
  "sub": "usr_99812481",
  "aud": "https://api.enterprise.com",
  "exp": 1711933200,
  "scope": "payments:write",
  "cnf": {
    "jkt": "0ZcOCORZTXDEU2O9_j_u-Jsl2xOqHwQ2o5uE5Fm3k8s"
  }
}
```
* `cnf.jkt`: JSON Web Key SHA-256 Thumbprint (RFC 7638) dari kunci publik yang dikirim dalam DPoP proof.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Implementasi produksi berikut mencakup:
1. **Rego Policy (OPA)** untuk aturan otorisasi ABAC tingkat tinggi.
2. **Go Middleware (API Gateway PEP)** yang memverifikasi DPoP Proof, mencocokkan `cnf.jkt`, dan memanggil evaluator OPA.

### File 1: Kebijakan OPA ABAC (`policy.rego`)

```rego
package enterprise.api.authz

import future.keywords.in

default allow = false

# Definisi batas jam kerja (08:00 - 18:00 UTC)
default is_working_hours = false
is_working_hours {
    current_hour := time.clock(input.context.timestamp)[0]
    current_hour >= 8
    current_hour < 18
}

# Subnet internal korporat
corporate_subnets := ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]

client_ip_allowed {
    some subnet in corporate_subnets
    net.cidr_contains(subnet, input.context.source_ip)
}

# Evaluasi Keputusan Utama (Allow Rules)
allow {
    # 1. Pastikan token ditandatangani dan valid secara DPoP
    input.token.is_dpop_bound == true
    input.token.dpop_jkt_matched == true

    # 2. Periksa apakah operasi bersifat read-only
    input.request.method == "GET"
    "api:read" in input.token.scopes
}

allow {
    # 3. Operasi sensitif tingkat tinggi (Financial Transfer/Write)
    input.request.method in ["POST", "PUT", "DELETE"]
    "api:write" in input.token.scopes
    
    # Verifikasi level jaminan autentikasi (OIDC ACR - Multi-Factor Authentication)
    input.token.claims.acr == "urn:enterprise:loa:mfa"

    # Evaluasi Kontekstual Lingkungan (ABAC)
    is_working_hours
    client_ip_allowed

    # Verifikasi batasan kepemilikan resource atau peran otorisasi tinggi
    user_has_resource_access
}

# Rule kepemilikan resource
user_has_resource_access {
    # Pengguna dengan role Super Admin memiliki izin bypass
    "ROLE_SUPER_ADMIN" in input.token.claims.roles
}

user_has_resource_access {
    # Operasi dibatasi hanya pada data departemen milik pengguna
    input.token.claims.department == input.resource.target_department
    input.resource.classification != "RESTRICTED"
}
```

### File 2: PEP Middleware Implementation di Go (`pep_middleware.go`)

```go
package main

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
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

// In-memory cache sederhana untuk anti-replay attack DPoP (Gunakan Redis pada cluster produksi)
var (
	jtiCache   = make(map[string]time.Time)
	cacheMutex sync.Mutex
)

type PEPHandler struct {
	opaQuery rego.PreparedEvalQuery
}

func NewPEPHandler(ctx context.Context, regoPolicyPath string) (*PEPHandler, error) {
	query, err := rego.New(
		rego.Query("data.enterprise.api.authz.allow"),
		rego.Load([]string{regoPolicyPath}, nil),
	).PrepareForEval(ctx)

	if err != nil {
		return nil, fmt.Errorf("gagal kompilasi OPA query: %w", err)
	}

	return &PEPHandler{opaQuery: query}, nil
}

// Menghitung SHA-256 JWK Thumbprint sesuai RFC 7638 (untuk EC P-256)
func calculateJWKThumbprint(jwk map[string]interface{}) (string, error) {
	crv, _ := jwk["crv"].(string)
	kty, _ := jwk["kty"].(string)
	x, _ := jwk["x"].(string)
	y, _ := jwk["y"].(string)

	if crv == "" || kty == "" || x == "" || y == "" {
		return "", errors.New("parameter JWK tidak lengkap untuk penentuan thumbprint")
	}

	// Canonical JSON string (urutan alfabetikal wajib sesuai RFC 7638)
	canonicalJSON := fmt.Sprintf(`{"crv":"%s","kty":"%s","x":"%s","y":"%s"}`, crv, kty, x, y)
	hash := sha256.Sum256([]byte(canonicalJSON))
	return base64.RawURLEncoding.EncodeToString(hash[:]), nil
}

func (h *PEPHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// 1. Ekstrak Header DPoP & Authorization
	authHeader := r.Header.Get("Authorization")
	dpopHeader := r.Header.Get("DPoP")

	if !strings.HasPrefix(authHeader, "DPoP ") || dpopHeader == "" {
		http.Error(w, `{"error": "invalid_token", "error_description": "Memerlukan skema DPoP token binding"}`, http.StatusUnauthorized)
		return
	}

	rawAccessToken := strings.TrimPrefix(authHeader, "DPoP ")

	// 2. Parse DPoP Proof Token Unverified (Hanya untuk ekstraksi Header & Body sebelum validasi signature)
	parser := jwt.NewParser(jwt.WithoutClaimsValidation())
	dpopToken, _, err := parser.ParseUnverified(dpopHeader, jwt.MapClaims{})
	if err != nil {
		http.Error(w, `{"error": "invalid_dpop_proof"}`, http.StatusBadRequest)
		return
	}

	jwkRaw, ok := dpopToken.Header["jwk"].(map[string]interface{})
	if !ok {
		http.Error(w, `{"error": "dpop_missing_jwk"}`, http.StatusBadRequest)
		return
	}

	calculatedThumbprint, err := calculateJWKThumbprint(jwkRaw)
	if err != nil {
		http.Error(w, `{"error": "invalid_jwk_structure"}`, http.StatusBadRequest)
		return
	}

	dpopClaims, ok := dpopToken.Claims.(jwt.MapClaims)
	if !ok {
		http.Error(w, `{"error": "invalid_claims"}`, http.StatusBadRequest)
		return
	}

	// 3. Verifikasi Klaim DPoP Proof (htm, htu, jti anti-replay)
	htm, _ := dpopClaims["htm"].(string)
	htu, _ := dpopClaims["htu"].(string)
	jti, _ := dpopClaims["jti"].(string)

	if !strings.EqualFold(htm, r.Method) {
		http.Error(w, `{"error": "dpop_htm_mismatch"}`, http.StatusBadRequest)
		return
	}

	// Validasi normalisasi URL (skema + host + path)
	targetURI := fmt.Sprintf("https://%s%s", r.Host, r.URL.Path)
	if htu != targetURI {
		http.Error(w, fmt.Sprintf(`{"error": "dpop_htu_mismatch", "expected": "%s"}`, targetURI), http.StatusBadRequest)
		return
	}

	// Verifikasi Anti-Replay Cache
	cacheMutex.Lock()
	if _, exists := jtiCache[jti]; exists {
		cacheMutex.Unlock()
		http.Error(w, `{"error": "dpop_replay_detected"}`, http.StatusUnauthorized)
		return
	}
	jtiCache[jti] = time.Now()
	cacheMutex.Unlock()

	// 4. Parse Access Token (Mocked decoding payload untuk demo ini)
	accessTokenObj, _, err := parser.ParseUnverified(rawAccessToken, jwt.MapClaims{})
	if err != nil {
		http.Error(w, `{"error": "invalid_access_token"}`, http.StatusUnauthorized)
		return
	}
	accessClaims := accessTokenObj.Claims.(jwt.MapClaims)

	// Validasi cnf.jkt matching
	var jktMatched = false
	if cnf, ok := accessClaims["cnf"].(map[string]interface{}); ok {
		if jkt, ok := cnf["jkt"].(string); ok {
			if jkt == calculatedThumbprint {
				jktMatched = true
			}
		}
	}

	if !jktMatched {
		http.Error(w, `{"error": "dpop_token_binding_mismatch"}`, http.StatusUnauthorized)
		return
	}

	// 5. Susun Input Evaluasi Kebijakan OPA (ABAC context)
	input := map[string]interface{}{
		"token": map[string]interface{}{
			"is_dpop_bound":     true,
			"dpop_jkt_matched":  jktMatched,
			"scopes":            strings.Split(accessClaims["scope"].(string), " "),
			"claims":            accessClaims,
		},
		"request": map[string]interface{}{
			"method": r.Method,
			"path":   r.URL.Path,
		},
		"resource": map[string]interface{}{
			"target_department": "FINANCE",
			"classification":    "HIGH",
		},
		"context": map[string]interface{}{
			"source_ip": r.RemoteAddr,
			"timestamp": time.Now().Unix(),
		},
	}

	// 6. Eksekusi Evaluasi PDP (OPA)
	results, err := h.opaQuery.Eval(ctx, rego.EvalInput(input))
	if err != nil || len(results) == 0 {
		http.Error(w, `{"error": "internal_pdp_failure"}`, http.StatusInternalServerError)
		return
	}

	allowed, ok := results[0].Bindings["allow"].(bool)
	if !ok || !allowed {
		http.Error(w, `{"error": "forbidden_by_policy"}`, http.StatusForbidden)
		return
	}

	// Otorisasi Berhasil -> Teruskan request ke service downstream
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status": "success", "message": "Access granted via DPoP & ABAC verification"}`))
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektural | Opsi A: Mutual TLS (RFC 8705) | Opsi B: DPoP (RFC 9449) | Dampak & Mitigasi Desain |
| :--- | :--- | :--- | :--- |
| **Layer Eksekusi** | Layer 4 (Transport / TLS) | Layer 7 (Application / HTTP) | mTLS menuntut terminasi sertifikat klien di gateway paling depan. DPoP dapat melewati multi-hop reverse proxy/CDN tanpa dekripsi TLS. |
| **Beban Klien** | Mengelola sertifikat X.509 dan PKI provisioning. | Membuat pasangan kunci asimetris lokal (WebCrypto/Secure Enclave). | DPoP jauh lebih ramah untuk SPA dan Mobile; mTLS lebih cocok untuk komunikasi Service-to-Service (East-West). |
| **Overhead CPU Gateway** | Sangat rendah (dihandle hardware offloading TLS). | Moderat (verifikasi signature JWT tambahan untuk setiap panggilan API). | Terapkan caching verifikasi kunci publik DPoP dan ephemeral session binding untuk request berulang berfrekuensi tinggi. |

| Model Otorisasi | RBAC (Role-Based) | ABAC (Attribute-Based via OPA) | Dampak & Mitigasi Desain |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Desain** | Rendah (Role statis di token claim). | Tinggi (Memerlukan data pipeline atribut dan pemodelan Rego). | Gunakan RBAC hanya untuk otentikasi coarse-grained level gateway; operasikan ABAC untuk fine-grained domain logic. |
| **Performa Evaluasi** | $O(1)$ string comparison di gateway. | $O(n)$ evaluasi graph rule engine berbasis konteks. | Gunakan OPA embedded compiler / in-process WebAssembly (Wasm) targets di gateway untuk menekan latensi sub-milidetik. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Phantom Token Pattern:** Jangan mengekspos JWT token internal yang berisi atribut sensitif ke public consumer. Gateway harus mengonversi *Opaque Reference Token* dari public client menjadi *Cryptographically Signed JWT* sebelum diteruskan ke microservice internal.
2. **Karantina JTI Anti-Replay Secara Terdistribusi:** Validasi `jti` pada DPoP proof wajib memiliki TTL ketat (maksimal 60–120 detik) dan disimpan dalam distributed fast-cache (Redis/Dragonfly cluster) menggunakan operasi atomic `SETNX` untuk mencegah *concurrent replay attack*.
3. **Pushed Authorization Requests (PAR) Wajib Diaktifkan:** Seluruh parameter otorisasi transaksi finansial harus melalui endpoint PAR dengan masa berlaku `request_uri` maksimum 60 detik.
4. **JWKS Rotation Tanpa Downtime:**
   * Jangan hardcode kunci RSA/ECDSA.
   * Buat mekanisme polling atau cache invalidation JWKS berbasis header `kid` (Key ID).
   * Gateway harus mendukung minimal dua kunci aktif sekaligus saat fase transisi rotasi kunci.
5. **Decouple PDP dari PEP:** Tempatkan OPA engine sebagai local sidecar (di Kubernetes pod yang sama via localhost) atau link OPA WebAssembly library secara native ke API Gateway untuk memangkas latensi network hop PDP.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Tidak Memvalidasi Hash Access Token (`ath`) pada DPoP:**
   * *Kesalahan:* Gateway hanya memvalidasi signature DPoP proof, tetapi tidak memeriksa claim `ath`.
   * *Eksploitasi:* Penyerang dapat mencuri DPoP proof sah yang beredar dan memasangkannya dengan access token curian lain yang berbeda.
2. **Pengabaian Normalisasi URI (`htu` Validation):**
   * *Kesalahan:* Membandingkan `htu` menggunakan perbandingan string mentah tanpa melakukan sanitasi normalisasi (query params, trailing slash, lowercasing domain).
   * *Dampak:* Validasi gagal secara palsu (*false rejection*) atau bypass lolos jika penyerang menyisipkan variasi path traversal.
3. **Membocorkan Metadata PDP ke Client (Information Disclosure):**
   * *Kesalahan:* Mengembalikan isi error evaluasi Rego secara gamblang (`{"error": "denied by rule: department != 'FINANCE'"}`).
   * *Perbaikan:* Selalu kembalikan respons terstandarisasi generik `403 Forbidden` ke eksternal, dan simpan log detail audit evaluasi hanya di sistem internal collector (OpenTelemetry/ELK).
4. **Membiarkan Algoritma Kriptografi 'none' atau Key Substitution:**
   * *Kesalahan:* Mempercayai claim `alg` dari header JWT client tanpa *whitelisting* eksplisit pada server parser.
   * *Perbaikan:* Tolak secara absolut algoritma simetris ketika server mengharapkan asimetris, dan tolak algoritma `none`.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario
Sebuah institusi perbankan mengimplementasikan standardisasi API PSD2 / FAPI. Anda ditugaskan membangun pipeline keamanan yang menghalangi replay attack dan memberlakukan kontrol akses berbasis atribut.

### Tugas:
1. **Latihan 1 (DPoP Proof Construction):**
   Tulis script Node.js / Python sederhana yang membangkitkan pasangan kunci EC P-256, membuat DPoP proof JWT yang valid untuk request `POST https://api.bank.com/v1/accounts`, dan menyertakan hash SHA-256 dari access token dummy `at_secret_xyz123`.
2. **Latihan 2 (Rego ABAC Policy Enhancement):**
   Modifikasi kebijakan OPA Rego pada Bagian 09 untuk menambahkan aturan berikut:
   * Jika nilai transaksi (`input.resource.amount`) lebih dari Rp 100.000.000, request hanya diizinkan jika claim `acr` bernilai `urn:bank:loa:biometric` DAN request dilakukan dari range subnet VPN kantor pusat `10.200.0.0/16`.
3. **Latihan 3 (PEP Gateway Fail-Safe Logic):**
   Modifikasi middleware Go pada Bagian 09 untuk menangani skenario di mana endpoint OPA mengalami *timeout* (>200ms). Gateway harus menerapkan prinsip *Fail-Closed* (menolak akses secara default dengan status 503) dan menghasilkan log trace audit terstruktur.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

**1. Mengapa OAuth 2.1 secara tegas mendepresiasi skema Implicit Flow?**
* A. Karena Authorization Code Flow membutuhkan resource CPU server yang lebih sedikit.
* B. Karena parameter token dikembalikan melalui URI fragment pada browser, sehingga mudah bocor via log server, referer headers, dan history browser.
* C. Karena Implicit Flow tidak mendukung algoritma enkripsi TLS 1.3.
* D. Karena token yang diterbitkan oleh Implicit Flow tidak dapat divalidasi oleh API Gateway.

**2. Dalam spesifikasi DPoP (RFC 9449), apa fungsi spesifik dari claim `ath` di dalam payload DPoP Proof?**
* A. Menyimpan IP address publik dari client caller.
* B. Menautkan DPoP proof secara kriptografis ke Access Token yang bersangkutan guna mencegah pencurian proof untuk token lain.
* C. Menentukan masa kedaluwarsa private key milik client.
* D. Menampung konfigurasi Public Key Infrastructure (PKI) sertifikat root.

**3. Manakah dari skenario berikut yang menggambarkan keunggulan ABAC dibandingkan RBAC konvensional?**
* A. Memeriksa apakah user memiliki peran `ROLE_ADMIN`.
* B. Memeriksa apakah request HTTP menggunakan port 443 atau 8443.
* C. Membatasi pengeditan dokumen medis hanya untuk dokter penanggung jawab pasien, selama jam operasional poliklinik, dan dari terminal rumah sakit yang sah.
* D. Memvalidasi bahwa access token ditandatangani menggunakan kunci RS256.

**4. Pada Financial-grade API (FAPI), apa peran utama dari mekanisme Pushed Authorization Requests (PAR)?**
* A. Mengirim Access Token langsung via WebSocket.
* B. Memindahkan parameter inisiasi otorisasi dari public query string di browser ke payload HTTP POST backchannel yang terotentikasi langsung ke server otorisasi.
* C. Mengganti kebutuhan akan sertifikat mTLS pada layer transport.
* D. Mengotomatisasi rotasi JWKS secara berkala.

**5. Jika sebuah access token berbasis DPoP dicuri oleh pihak ketiga melalui memory-dump, apakah penyerang dapat menggunakannya untuk memanggil API Gateway?**
* A. Ya, karena access token memuat semua scope yang diperlukan.
* B. Ya, asalkan penyerang mengetahui URL endpoint gateway.
* C. Tidak, karena penyerang tidak memiliki private key client untuk membuat signature DPoP proof baru dengan `jti`, timestamp, dan `ath` yang valid.
* D. Tergantung apakah API Gateway menggunakan protokol HTTP/2 atau HTTP/1.1.

### Kunci Jawaban:
1. **B** — Fragment URI URL pada Implicit flow rentan terekspos ke komponen yang tidak terpercaya pada user-agent.
2. **B** — `ath` (Access Token Hash) mengikat proof JWT dengan access token spesifik yang sedang digunakan.
3. **C** — ABAC mengombinasikan multi-variabel konteks (subjek, resource, waktu, environment) yang tidak dapat diskalakan secara rasional oleh sistem RBAC statis.
4. **B** — PAR menyembunyikan parameter otorisasi dari pandangan publik/browser dan mencegah serangan tampering request URI.
5. **C** — Sifat *sender-constrained* DPoP membatalkan utilitas access token tanpa kepemilikan pasangan *private key* penandatangan proof.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **RFC 6749 & RFC 6750:** *The OAuth 2.0 Authorization Framework & Bearer Token Usage.*
* **RFC 9449:** *OAuth 2.0 Demonstrating Proof-of-Possession at the Application Layer (DPoP).*
* **RFC 8705:** *OAuth 2.0 Mutual-TLS Client Authentication and Certificate-Bound Access Tokens.*
* **RFC 9126:** *OAuth 2.0 Pushed Authorization Requests (PAR).*
* **RFC 9101:** *The OAuth 2.0 Authorization Framework: JWT-Secured Authorization Request (JAR) & JARM.*
* **OpenID Foundation:** *Financial-grade API (FAPI 1.0 / 2.0) Security Profile.*
* **NIST Special Publication 800-207:** *Zero Trust Architecture.*
* **Open Policy Agent (OPA) Documentation:** *Policy Language: Rego Specification (openpolicyagent.org).*

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **OAuth 2.1 Menghapus Anti-Pattern:** Mengeliminasi grant flows historis yang cacat (Implicit, ROPC) dan mewajibkan PKCE serta pencocokan URI absolut untuk memitigasi serangan manipulasi authorization code.
2. **Token Binding Menutup Celah Terbesar Bearer Tokens:** Pencurian access token tidak lagi berakibat fatal jika menggunakan *sender-constrained tokens*. Kunci asimetris terikat langsung pada token, baik pada Layer 4 via sertifikat mTLS (`x5t#S256`) maupun Layer 7 via DPoP (`cnf.jkt`).
3. **FAPI Membawa Standar Regulasi Ketat:** Melalui PAR dan JARM, interaksi otorisasi bebas dari kebocoran log URL browser dan manipulasi integritas response.
4. **Decoupled ABAC Menyelesaikan Skalabilitas Otorisasi:** Memisahkan *enforcement* (Gateway/PEP) dari *decision* (OPA/PDP) menggunakan model ABAC memungkinkan penegakan aturan granular multi-atribut secara dinamis tanpa kompilasi ulang microservice.

---

## SEKSI 17 — GLOSARIUM

* **PEP (Policy Enforcement Point):** Komponen arsitektural (seperti API Gateway) yang mencegat permintaan layanan, meminta keputusan otorisasi ke PDP, dan menegakkan keputusan tersebut.
* **PDP (Policy Decision Point):** Entitas logis terpusat (seperti OPA) yang mengevaluasi kebijakan keamanan berdasarkan atribut input dan aturan formal untuk membuat keputusan (*permit/deny*).
* **DPoP (Demonstrating Proof-of-Possession):** Protokol pengikatan token lapisan aplikasi yang membuktikan kepemilikan kunci privat oleh klien saat meminta token dan mengakses resource.
* **Thumbprint (JWK / Cert):** Hash kriptografis deterministik dari representasi kanonikal kunci publik atau sertifikat X.509, digunakan sebagai tanda pengenal unik ringkas.
* **PAR (Pushed Authorization Requests):** Standar pengiriman parameter otorisasi langsung ke server otorisasi melalui saluran HTTP POST terproteksi sebelum redirect dilakukan.
* **JARM (JWT Secured Authorization Response Mode):** Mekanisme penyampaian parameter respons otorisasi dalam payload JWT yang ditandatangani dan/atau dienkripsi.
* **Zero Trust:** Filosofi arsitektur keamanan yang menuntut verifikasi identitas dan hak akses secara terus-menerus tanpa memandang lokasi jaringan pemohon.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan Materi:** Pastikan peserta memahami secara absolut perbedaan mendasar antara *Authentication* (siapa Anda / OIDC) dan *Authorization* (apa yang boleh Anda lakukan / OAuth 2.1 & ABAC). Banyak engineer senior masih keliru menganggap JWT OIDC ID Token dapat digunakan langsung sebagai Access Token ke API Gateway.
* **Titik Hambat Mahasiswa (Gotchas):** 
  * Perhitungan Canonical Thumbprint RFC 7638 untuk DPoP JWK sering memicu bug karena ketidaksesuaian spasi atau urutan field JSON. Tunjukkan mengapa urutan alfabetik field (`crv`, `kty`, `x`, `y`) adalah keharusan mutlak.
  * Mahasiswa sering mengabaikan latensi network antara Gateway (PEP) dan OPA (PDP). Tekankan pentingnya deployment sidecar OPA di localhost node atau Wasm compilation untuk lingkungan produksi berkinerja tinggi.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 2.0.0 (Current):**
  * Konsolidasi kurikulum OAuth 2.1 terbaru menggantikan draft spesifikasi 2.0 warisan.
  * Penambahan implementasi FAPI 2.0, deep-dive RFC 9449 (DPoP), dan RFC 8705 (mTLS).
  * Penambahan source code runnable Go PEP Middleware terintegrasi dengan runtime OPA Rego.
* **Versi 1.1.0:**
  * Penambahan modul ABAC dasar dan diagram evaluasi XACML/Rego.
* **Versi 1.0.0:**
  * Rilis inisial materi arsitektur keamanan OAuth 2.0 & OIDC.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `API-DES-0504` — High-Performance API Gateway Patterns: Rate Limiting, Caching, & Circuit Breaking.
* **Modul Ini:** `API-DES-0601` — Enterprise API Security, Identity, & Governance: OAuth 2.1, OIDC, FAPI, mTLS, Token Binding DPoP, Authorization Policy OPA Rego & ABAC.
* **Modul Berikutnya:** `API-DES-0602` — Event-Driven API Architecture & Governance: AsyncAPI, CloudEvents, Idempotency, & Outbox Patterns.