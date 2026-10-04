# Kurikulum Enterprise: Forward Deployed Engineer (FDE)
## Kategori: 06-Architecture-and-System-Design
### Bab 05: Keamanan Enterprise & Zero Trust
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Forward Deployed Engineer (FDE) diharapkan mampu:

1. **Mendesain dan Mengimplementasikan Arsitektur Zero Trust (NIST SP 800-207)** pada lingkungan *hostile/heterogeneous* milik klien enterprise (on-premise, air-gapped, multi-tenant hybrid cloud).
2. **Mengonfigurasi Service-to-Service Cryptographic Identity** menggunakan standar SPIFFE/SPIRE untuk mengatasi problem *Secret Zero* tanpa bergantung pada static credentials.
3. **Mengonstruksi Policy Enforcement Point (PEP) dan Policy Decision Point (PDP)** terdistribusi menggunakan Envoy Proxy dan Open Policy Agent (OPA) via protokol gRPC `ext_authz`.
4. **Mengimplementasikan Token Exchange Engine (RFC 8693)** untuk memetakan identitas upstream enterprise (SAML 2.0 / OIDC dari Okta, Azure AD, PingFederate) ke dalam micro-identity berumur pendek (*ephemeral short-lived credentials*).
5. **Mendiagnosis dan Memitigasi Regresi Performa Latensi** akibat kriptografi mTLS L7 dan evaluasi kebijakan otorisasi runtime pada skala *high-throughput* (>10.000 RPS).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:

* **Kriptografi Terapan & PKI**: Mekanisme TLS 1.3 handshake, rantai sertifikat X.509 (Root CA, Intermediate CA, Leaf), parsing struktur ASN.1, dan verifikasi JWT/JWS/JWE.
* **Jaringan Sistem Tingkat Rendah**: Model OSI L4 vs L7, TCP connection pooling, HTTP/2 multiplexing, gRPC over HTTP/2, serta manipulasi paket via Linux primitives (iptables, eBPF, network namespaces).
* **Container Orchestration Internals**: Arsitektur internal Kubernetes (Kube-API, etcd, CRI, CNI), konsep Pod mutation via Admission Webhooks, dan arsitektur Envoy Service Mesh (Data Plane vs Control Plane).
* **Bahasa Pemrograman**: Kemahiran membaca dan menulis kode dalam bahasa **Go** (tingkat lanjut) untuk integrasi SDK Envoy/OPA serta bahasa deklaratif **Rego**.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi Zero Trust oleh seorang FDE di lingkungan enterprise tidak boleh berasumsi bahwa perimeter jaringan (firewall, VPN) bersifat aman. Seluruh paket jaringan diperlakukan seolah-olah ditransmisikan melalui internet publik.

Arsitektur produksi Zero Trust dibangun di atas model pemisahan kontrol:

```
+-----------------------------------------------------------------------------+
|                          CONTROL PLANE (Trust Engine)                       |
|                                                                             |
|  +---------------------+      Federation     +--------------------------+   |
|  | Enterprise IdP      |<===================>| SPIRE Server             |   |
|  | (Okta/Azure AD/Ping)|                     | (PKI Root of Trust)      |   |
|  +---------------------+                     +--------------------------+   |
|            |                                              |                 |
|       OIDC Tokens                                   Issues SVIDs            |
|            |                                              |                 |
|            v                                              v                 |
|  +---------------------+                     +--------------------------+   |
|  | Token Exchange Svc  |                     | SPIRE Agent (Node Daemon)|   |
|  | (RFC 8693 STS)      |                     | (Workload Attestation)   |   |
|  +---------------------+                     +--------------------------+   |
+------------|----------------------------------------------|-----------------+
             | Downstream Identity Credentials              | Local Workload API
+------------v----------------------------------------------v-----------------+
|                           DATA PLANE (Workload Node)                        |
|                                                                             |
|   +---------------------------------------------------------------------+   |
|   | Pod / Virtual Machine Boundary                                      |   |
|   |                                                                     |   |
|   |   +------------------+    gRPC Check     +---------------------+    |   |
|   |   |  Envoy Proxy     |==================>| Open Policy Agent   |    |   |
|   |   |  (PEP)           |                   | (PDP - Local In-Mem)|    |   |
|   |   +------------------+                   +---------------------+    |   |
|   |      ^            |                             ^                   |   |
|   | mTLS | Ingress    | Cleartext IPC /             | Dynamic Policy    |   |
|   | L7   |            | Local Loopback              | Sync              |   |
|   |      |            v                             |                   |   |
|   |   +------------------+                   +---------------------+    |   |
|   |   | App Workload     |                   | Local Bundle Cache  |    |   |
|   |   | (FDE Target App) |                   | (Signed Tarball)    |    |   |
|   |   +------------------+                   +---------------------+    |   |
|   +---------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------+
```

#### A. Identitas Kriptografis Beban Kerja (SPIFFE/SPIRE)

Alih-alih menyuntikkan token statis, database credentials, atau API key, workload diidentifikasi melalui **SPIFFE ID**:
$$\text{spiffe://trust-domain/ns/}\{namespace\}\text{/sa/}\{serviceaccount\}$$

1. **Node Attestation**: SPIRE Agent memverifikasi identitas host fisik/virtual tempat ia berjalan menggunakan bukti kriptografis hardware (AWS IID, GCP GCE Attestation, atau TPM 2.0 endorsement key).
2. **Workload Attestation**: SPIRE Agent menginterogasi kernel Linux lokal melalui UNIX Domain Socket (`/run/spire/sockets/agent.sock`) guna memeriksa `PID`, `cgroup`, binary path, dan metadata container (misal: Kubernetes Namespace, ServiceAccount UID) dari aplikasi target.
3. **SVID Issuance**: Jika valid, Agent menerbitkan **X.509 SVID (SPIFFE Verifiable Identity Document)** berumur pendek (umumnya 10 menit hingga 1 jam) langsung ke memori proses Envoy Proxy. Kunci privat tidak pernah menyentuh persistent storage (disk).

#### B. Dynamic Policy Enforcement (Envoy + OPA)

* **PEP (Envoy Proxy)**: Mengintersepsi setiap koneksi TCP/HTTP masuk dan keluar. Selama fase handshake TLS, Envoy memvalidasi X.509 SVID milik peer, mengekstrak SPIFFE ID dari `Subject Alternative Name (SAN)`, dan memverifikasi sertifikat terhadap Root CA dari Trust Bundle.
* **PDP (Open Policy Agent)**: Berjalan sebagai sidecar process atau node daemon yang berkomunikasi dengan Envoy via API `Envoy External Authorization (ext_authz)` berbasis gRPC. Envoy mengirimkan `CheckRequest` yang berisi metadata jaringan (IP sumber/tujuan, port), atribut mTLS (SAN SPIFFE ID), dan HTTP context (headers, path, method). OPA mengevaluasi aturan ABAC (Attribute-Based Access Control) dalam hitungan sub-milidetik secara in-memory.

#### C. Arbitrasi Identitas Eksternal (RFC 8693 Token Exchange)

Ketika sistem yang di-deploy FDE harus mengonsumsi data dari klien enterprise, token pengguna (misal: JSON Web Token dari Azure AD) harus ditukar dengan token domain internal yang dibatasi hak aksesnya (*down-scoping*). FDE mengimplementasikan Security Token Service (STS) yang memverifikasi tanda tangan IdP upstream, menerapkan pemetaan grup/peran (*claims transformation*), dan mengeluarkan cryptographic assertions internal.

---

### 4. Why & What

| Dimensi | Pendekatan Perimeter Tradisional | Pendekatan Zero Trust Enterprise (FDE) |
| :--- | :--- | :--- |
| **Batas Keamanan** | Jaringan fisik, VLAN, IP Subnet, VPN gateway | Kriptografi per-request, workload attestation, identitas ephemeral |
| **Asumsi Ancaman** | Intranet dipercaya (*trusted internal network*) | Jaringan dianggap selalu telah disusupi (*assumed breach*) |
| **Manajemen Kredensial** | Static API Keys, Vault AppRole static secret, disk-persisted certs | Dynamic memory-only SVIDs, rotasi otomatis, zero-static secrets |
| **Kontrol Akses** | Kasar (L3/L4 IP:Port Whitelisting) | Sangat Terperinci (L7 Method, Path, Payload Claims, Contextual ABAC) |
| **Audit & Forensik** | Log firewall tanpa korelasi identitas aplikasi | Log terstruktur berbasis SPIFFE ID dan trace konteks kriptografis |

**Mengapa FDE Harus Menerapkan Pola Ini?**
Klien enterprise sering kali memaksakan integrasi platform ke dalam arsitektur multi-tenant milik mereka, di mana tim infosec internal menolak memberikan akses root, melarang hardcoded secrets dalam konfigurasi, dan mewajibkan rotasi kunci setiap 24 jam. Tanpa otomatisasi SPIFFE/Envoy/OPA, FDE akan terjebak dalam *operational nightmare* untuk memperbarui sertifikat manual dan mengelola tiket firewall yang rapuh.

---

### 5. How (Workflow Detail)

Berikut adalah alur eksekusi per-request (*request lifecycle*) end-to-end:

```
[Downstream Client]      [Envoy Proxy PEP]         [SPIRE Agent]       [OPA PDP]        [Upstream App]
        |                        |                       |                 |                  |
        |--- 1. TLS Handshake -->|                       |                 |                  |
        |    (Present SVID)      |<-- 2. Fetch/Renew ----|                 |                  |
        |                        |       Certs (mTLS)    |                 |                  |
        |                        |                       |                 |                  |
        |<-- 3. Mutual Verif. -->| (SAN Validated)       |                 |                  |
        |                        |                                         |                  |
        |--- 4. HTTP POST /data -|                                         |                  |
        |    (Bearer JWT)        |--- 5. ext_authz CheckRequest ---------->|                  |
        |                        |       (Path, Headers, SPIFFE-ID)        |                  |
        |                        |                                         |-- 6. Evaluate -->|
        |                        |                                         |      Rego AST    |
        |                        |<-- 7. CheckResponse (OK + Mutated Hdr)--|                  |
        |                        |                                                            |
        |                        |--- 8. Forward Authorized Request ------------------------->|
        |                        |       (Includes Verified Enterprise Context)               |
        |                        |                                                            |
        |                        |<-- 9. HTTP 200 OK Response --------------------------------|
        |<-- 10. HTTP 200 OK ----|
```

1. **Bootstrap Identitas**: SPIRE Agent melakukan atestasi pod downstream dan Envoy Proxy. SVID diinjeksikan ke Envoy melalui Secret Discovery Service (SDS) API gRPC di memori.
2. **Koneksi Klien**: Klien memulai handshake mTLS dengan Envoy PEP.
3. **Validasi Kriptografi**: Envoy mengekstrak SPIFFE ID klien dari sertifikat X.509 dan memvalidasinya terhadap CA bundle yang disediakan SPIRE.
4. **Intersepsi Data Plane**: Klien mengirimkan request L7 (HTTP/gRPC) dengan membawa payload dan token identitas upstream.
5. **Delegasi Otorisasi**: Envoy menunda pemrosesan request dan merakit objek `CheckRequest` gRPC yang dikirim ke OPA PDP via localhost domain socket atau direct TCP.
6. **Evaluasi Kebijakan**: OPA mengurai payload JSON dari request, memvalidasi klaim token, mencocokkan SPIFFE ID pengirim dengan rule ABAC, dan memastikan hak akses diberikan.
7. **Mutasi Konteks**: OPA mengembalikan instruksi `Allowed: true` beserta header HTTP baru (misal: `X-Federated-User: alice@enterprise.com`, `X-Allowed-Scopes: read,write`).
8. **Forwarding Aman**: Envoy menyalurkan request yang telah divalidasi dan dimutasi ke aplikasi backend melalui secure loopback interface.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata: Konsulat Diplomatik dengan Pengawalan Ketat

* **Jaringan Tradisional**: Gerbang perumahan klaster. Sekali seseorang melewati satpam di pos depan komplek, dia bebas mengetuk dan memasuki setiap rumah tanpa ada yang memeriksa lagi.
* **Arsitektur Zero Trust**:
  * **SPIRE** bertindak sebagai **Kementerian Luar Negeri**. Kementerian ini memverifikasi dokumen fisik pemohon (hardware attestation) dan mengeluarkan **Paspor Diplomatik Resmi (SVID)** yang memiliki masa berlaku hanya 1 jam.
  * **Envoy Proxy** adalah **Penjaga Pintu Ruangan**. Ia menolak berbicara dengan siapa pun yang tidak mengenakan lencana resmi yang dapat diverifikasi sidik jarinya secara matematis (mTLS).
  * **OPA** adalah **Petugas Protokoler & Aturan Hukum**. Setiap kali seorang diplomat ingin membuka map dokumen di suatu meja, petugas memeriksa buku hukum: *"Apakah diplomat dari negara X dengan status Y boleh membaca berkas level Z pada jam kerja ini?"* Jika ya, pintu map dibuka; jika tidak, penolakan langsung dilakukan di tempat.

#### Topologi Modus Produksi Forward Deployed Architecture

```
                    +----------------------------------------+
                    |    Enterprise Identity Provider        |
                    |    (Azure AD / Ping Identity)          |
                    +----------------------------------------+
                                        | (OIDC Metadata Endpoint)
                                        v
+------------------------------------------------------------------------------------+
| CUSTOMER AIR-GAPPED / HYBRID VPC INFRASTRUCTURE                                    |
|                                                                                    |
|  +------------------------+                        +----------------------------+  |
|  | SPIRE Server Cluster   |                        | Token Exchange STS Engine  |  |
|  | - SQLite/Postgres DB   |                        | - RFC 8693 Impl (Go)       |  |
|  | - Upstream Enterprise  |                        | - JWKS Local Cache         |  |
|  |   CA Integration       |                        +----------------------------+  |
|  +------------------------+                                      |                 |
|             ^                                                    |                 |
|             | SPIFFE Workload API (mTLS)                         |                 |
|             v                                                    v                 |
|  +------------------------------------------------------------------------------+  |
|  | Kubernetes Worker Node                                                       |  |
|  |                                                                              |  |
|  |  +-----------------------+     Attests Kernel Metadata                       |  |
|  |  | SPIRE Agent DaemonSet |==================================+                |  |
|  |  +-----------------------+                                  |                |  |
|  |             | SDS (In-Memory Unix Socket)                   |                |  |
|  |             v                                               v                |  |
|  |    +------------------+   Envoy ext_authz (gRPC)   +------------------+      |  |
|  |    | Envoy Proxy      |===========================>| Open Policy      |      |  |
|  |    | (Sidecar PEP)    |                            | Agent (PDP)      |      |  |
|  |    +------------------+                            +------------------+      |  |
|  |             |                                               |                |  |
|  |             | Localhost IPC                                 | Dynamic Rules  |  |
|  |             v                                               v                |  |
|  |    +-------------------------------------------------------------------+     |  |
|  |    | Enterprise Target Workload Pod                                    |     |  |
|  |    | (Fintech Core Engine / Data Processing Platform)                  |     |  |
|  |    +-------------------------------------------------------------------+     |  |
|  +------------------------------------------------------------------------------+  |
+------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Kebijakan OPA Rego Dasar (Path & Role Whitelisting)

File: `policy_simple.rego`
```rego
package enterprise.simple_authz

default allow = false

# Whitelist HTTP Methods and Roles
allow {
    input.method == "GET"
    input.path == "/healthz"
}

allow {
    input.method == "POST"
    input.path == "/api/v1/telemetry"
    has_valid_role(input.jwt_claims.roles, "telemetry-writer")
}

has_valid_role(roles, required_role) {
    roles[_] == required_role
}
```

#### B. Practical Example: Production-Grade RFC 8693 Token Exchange & Envoy ext_authz Service

Di bawah ini adalah implementasi gRPC service level produksi dalam bahasa Go yang berfungsi ganda: sebagai **Envoy External Authorization (PEP integration)** sekaligus memverifikasi **RFC 8693 Token Exchange Claims**.

##### 1. Implementasi Server Otorisasi Go (ext_authz handler)

File: `cmd/authz-server/main.go`
```go
package main

import (
	"context"
	"crypto/rsa"
	"errors"
	"fmt"
	"net"
	"strings"
	"sync"
	"time"

	corev3 "github.com/envoyproxy/go-control-plane/envoy/config/core/v3"
	authv3 "github.com/envoyproxy/go-control-plane/envoy/service/auth/v3"
	typev3 "github.com/envoyproxy/go-control-plane/envoy/type/v3"
	"github.com/golang-jwt/jwt/v5"
	"google.golang.org/genproto/googleapis/rpc/status"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/reflection"
)

type TokenExchangeClaims struct {
	ActorIdentity string   `json:"act,omitempty"`
	Subject       string   `json:"sub"`
	Scopes        []string `json:"scp"`
	Audience      []string `json:"aud"`
	jwt.RegisteredClaims
}

type AuthServiceServer struct {
	authv3.UnimplementedAuthorizationServer
	mu         sync.RWMutex
	publicKeys map[string]*rsa.PublicKey
}

func NewAuthServiceServer() *AuthServiceServer {
	return &AuthServiceServer{
		publicKeys: make(map[string]*rsa.PublicKey),
	}
}

// Check implements Envoy ext_authz v3 gRPC contract
func (s *AuthServiceServer) Check(ctx context.Context, req *authv3.CheckRequest) (*authv3.CheckResponse, error) {
	httpReq := req.GetAttributes().GetRequest().GetHttp()
	if httpReq == nil {
		return s.deny(codes.InvalidArgument, "Non-HTTP traffic rejected"), nil
	}

	headers := httpReq.GetHeaders()
	authHeader, ok := headers["authorization"]
	if !ok || !strings.HasPrefix(authHeader, "Bearer ") {
		return s.deny(codes.Unauthenticated, "Authorization header missing or malformed"), nil
	}

	rawToken := strings.TrimPrefix(authHeader, "Bearer ")
	claims, err := s.validateToken(rawToken)
	if err != nil {
		return s.deny(codes.Unauthenticated, fmt.Sprintf("Invalid security token: %v", err)), nil
	}

	// SPIFFE ID extraction from downstream peer TLS certificate
	sourceIdentity := req.GetAttributes().GetSource().GetCertificate()
	downstreamSPIFFE := req.GetAttributes().GetSource().GetPrincipal()

	// Enforce Attribute-Based Access Control (ABAC) logic
	if !s.isAuthorized(claims, httpReq.GetMethod(), httpReq.GetPath(), downstreamSPIFFE) {
		return s.deny(codes.PermissionDenied, "Actor does not possess required scopes for resource"), nil
	}

	// Injection of enriched context into upstream headers
	return &authv3.CheckResponse{
		Status: &status.Status{Code: int32(codes.OK)},
		HttpResponse: &authv3.CheckResponse_OkResponse{
			OkResponse: &authv3.OkHttpResponse{
				Headers: []*corev3.HeaderValueOption{
					{
						Header: &corev3.HeaderValue{
							Key:   "x-authenticated-subject",
							Value: claims.Subject,
						},
					},
					{
						Header: &corev3.HeaderValue{
							Key:   "x-federated-actor",
							Value: claims.ActorIdentity,
						},
					},
					{
						Header: &corev3.HeaderValue{
							Key:   "x-peer-spiffe-id",
							Value: downstreamSPIFFE,
						},
					},
				},
			},
		},
	}, nil
}

func (s *AuthServiceServer) validateToken(tokenString string) (*TokenExchangeClaims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &TokenExchangeClaims{}, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodRSA); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		// In production, match `kid` against rotatable in-memory KeySet (JWKS)
		s.mu.RLock()
		defer s.mu.RUnlock()
		if key, exists := s.publicKeys["default-enterprise-key"]; exists {
			return key, nil
		}
		return nil, errors.New("public key for token validation not found")
	})

	if err != nil {
		return nil, err
	}

	if claims, ok := token.Claims.(*TokenExchangeClaims); ok && token.Valid {
		if claims.ExpiresAt != nil && claims.ExpiresAt.Time.Before(time.Now()) {
			return nil, errors.New("token expired")
		}
		return claims, nil
	}

	return nil, errors.New("invalid claims payload")
}

func (s *AuthServiceServer) isAuthorized(claims *TokenExchangeClaims, method string, path string, spiffeID string) bool {
	// Rule: Path /finance/settlement requires "finance:write" scope AND verified internal financial caller
	if strings.HasPrefix(path, "/finance/settlement") {
		if method == "POST" && s.hasScope(claims.Scopes, "finance:write") {
			// Enforce SPIFFE SAN identity check
			if strings.HasPrefix(spiffeID, "spiffe://prod.enterprise.internal/ns/settlement/sa/settlement-engine") {
				return true
			}
		}
		return false
	}
	return true
}

func (s *AuthServiceServer) hasScope(scopes []string, target string) bool {
	for _, scp := range scopes {
		if scp == target {
			return true
		}
	}
	return false
}

func (s *AuthServiceServer) deny(code codes.Code, message string) *authv3.CheckResponse {
	return &authv3.CheckResponse{
		Status: &status.Status{Code: int32(code), Message: message},
		HttpResponse: &authv3.CheckResponse_DeniedResponse{
			DeniedResponse: &authv3.DeniedHttpResponse{
				Status: &typev3.HttpStatus{
					Code: typev3.StatusCode(mapGRPCCodeToHTTP(code)),
				},
				Body: fmt.Sprintf(`{"error": "%s"}`, message),
			},
		},
	}
}

func mapGRPCCodeToHTTP(code codes.Code) int32 {
	switch code {
	case codes.InvalidArgument:
		return 400
	case codes.Unauthenticated:
		return 401
	case codes.PermissionDenied:
		return 403
	default:
		return 500
	}
}

func main() {
	listener, err := net.Listen("tcp", ":9001")
	if err != nil {
		panic(fmt.Sprintf("Failed to bind port 9001: %v", err))
	}

	grpcServer := grpc.NewServer()
	authServer := NewAuthServiceServer()

	authv3.RegisterAuthorizationServer(grpcServer, authServer)
	healthServer := health.NewServer()
	healthpb.RegisterHealthServer(grpcServer, healthServer)
	healthServer.SetServingStatus("", healthpb.HealthCheckResponse_SERVING)
	reflection.Register(grpcServer)

	fmt.Println("Enterprise ext_authz PDP operational on :9001")
	if err := grpcServer.Serve(listener); err != nil {
		panic(err)
	}
}
```

##### 2. Konfigurasi Envoy External Authorization Filter

File: `envoy-filter-config.yaml`
```yaml
static_resources:
  listeners:
  - name: ingress_listener
    address:
      socket_address: { address: 0.0.0.0, port_value: 8443 }
    filter_chains:
    - transport_socket:
        name: envoy.transport_sockets.tls
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.DownstreamTlsContext
          common_tls_context:
            tls_certificates:
            - certificate_chain: { filename: "/etc/ssl/certs/workload-cert.pem" }
              private_key: { filename: "/etc/ssl/certs/workload-key.pem" }
            validation_context:
              trusted_ca: { filename: "/etc/ssl/certs/spire-bundle.crt" }
              match_typed_subject_alt_names:
              - sanitizer_type: SANITIZER_TYPE_SPIFFE
                matcher:
                  exact: "spiffe://prod.enterprise.internal/ns/settlement/sa/settlement-engine"
      filters:
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
              - match: { prefix: "/" }
                route: { cluster: upstream_application_backend }
          http_filters:
          - name: envoy.filters.http.ext_authz
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.ext_authz.v3.ExtAuthz
              grpc_service:
                envoy_grpc:
                  cluster_name: ext_authz_pdp_cluster
                timeout: 0.250s
              transport_api_version: V3
              with_request_body:
                max_request_bytes: 1024
                pack_as_bytes: false
              failure_mode_allow: false
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router

  clusters:
  - name: ext_authz_pdp_cluster
    type: STATIC
    http2_protocol_options: {}
    load_assignment:
      cluster_name: ext_authz_pdp_cluster
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address: { address: 127.0.0.1, port_value: 9001 }

  - name: upstream_application_backend
    type: STATIC
    load_assignment:
      cluster_name: upstream_application_backend
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address: { address: 127.0.0.1, port_value: 8080 }
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Global Tier-1 Investment Bank
* **Sektor**: Perbankan Investasi & Kliring Keuangan.
* **Skala**: $4 triliun aset dalam penitipan, 18.000 microservices di 4 region (London, New York, Hong Kong, Tokyo), 65.000 transaksi/detik pada jam puncak perdagangan pasar.

#### Masalah Utama
Sebuah platform analitik kuantitatif yang dikerjakan oleh FDE harus di-deploy ke dalam datacenter *on-premise* klien (OpenShift) dan cloud klien (AWS GovCloud). Tim Infosec klien memberlakukan aturan absolut:
1. **Zero Static Credentials**: Tidak ada database password, AWS IAM secret keys, atau long-lived token yang disimpan dalam Kubernetes Secret atau environment variables.
2. **Data Sovereignty Compliance**: Permintaan kliring transaksi obligasi Euro tidak boleh diproses oleh node komputasi yang memiliki trust domain region US.
3. **Hard Latency Budget**: Kegagalan otorisasi tidak boleh menambah latensi lebih dari **1.8 milidetik** pada persentil p99.

#### Desain Solusi oleh FDE
1. **SPIRE Multi-Trust-Domain Federation**:
   FDE mengonfigurasi federasi trust domain antara `spiffe://eu.investmentbank.com` dan `spiffe://us.investmentbank.com`. Sertifikat root CA masing-masing disimpan di hardware HSM (Thales Luna HSM).
2. **eBPF-Assisted Node Attestation**:
   Atestasi pod tidak lagi menggunakan token Kubelet, melainkan eBPF cgroup checking untuk memvalidasi *digest* biner ELF sebelum SPIRE Agent menandatangani X.509 SVID.
3. **Optimasi Envoy + OPA PDP**:
   OPA dieksekusi sebagai in-process Go library langsung di dalam custom `ext_authz` binary via Unix Domain Sockets, meniadakan TCP stack overhead. Policy bundle dikompilasi secara ahead-of-time (AOT) ke bytecode WebAssembly (Wasm).

#### Dampak Arsitektur
* **Keamanan**: Mengeliminasi 100% insiden kebocoran credential token statis selama audit SOC2 Tipe II.
* **Performa**: Latensi PDP turun dari **8.4ms** (evaluasi HTTP REST eksternal awal) menjadi **0.32ms (p99)** dengan Envoy-OPA Unix Socket Wasm.
* **Auditability**: Setiap transaksi memiliki jejak audit kriptografis yang membuktikan identitas pod penerbit, identitas pengguna Active Directory, dan tanda tangan digital node fisik.

---

### 9. Trade-offs

| Parameter Arsitektur | Pilihan A (Pusat / Centralized PDP) | Pilihan B (Sidecar / Local PDP) | Analisis Trade-off FDE |
| :--- | :--- | :--- | :--- |
| **Latensi (p99)** | **Tinggi (10 - 50ms)**: Menambahkan hop jaringan L3 melintasi router internal. | **Sangat Rendah (< 1ms)**: Evaluasi lokal via memory atau Unix Domain Socket. | FDE wajib memilih Pilihan B untuk beban kerja *real-time processing* atau trading engine. |
| **Konsumsi Resource (Memory/CPU)** | **Efisien**: Policy engine hanya berjalan pada cluster dedicated kecil. | **Tinggi (Overhead Footprint)**: Setiap pod mengalokasikan 50-150MB RAM untuk Envoy + OPA. | Menjadi masalah pada cluster Kubernetes yang memiliki puluhan ribu pod micro-footprint. |
| **Konsistensi Kebijakan (State Convergence)** | **Instan / Strong Consistency**: Update aturan langsung berdampak global. | **Eventual Consistency**: Butuh waktu sinkronisasi bundle (1-10 detik) ke ribuan node. | Butuh mitigasi *version vectoring* agar tidak terjadi inkonsistensi otorisasi parsial. |
| **Kompleksitas Operasional** | **Rendah**: Cukup mengelola cluster otorisasi tunggal. | **Sangat Tinggi**: Membutuhkan otomasi SPIRE Agent, SDS rotation, dan monitoring lokal. | FDE memerlukan manifest deployment deklaratif (Helm/Kustomize) yang *bulletproof*. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Clock Skew Antar-Node Menyebabkan Bad Certificate Drop
* **Gejala**: Koneksi Envoy mTLS tiba-tiba drop dengan pesan: `SSL routines:OPENSSL_internal:CERTIFICATE_VERIFY_FAILED`.
* **Akar Masalah**: Drift waktu NTP antar node hypervisor melebihi masa validitas SVID yang pendek (misal masa berlaku SVID 10 menit, skew 60 detik).
* **Solusi**: Terapkan toleransi waktu `not_before` margin pada SPIRE Server/Agent (skew buffer 30-60 detik) dan sinkronisasikan NTP host ke Precision Time Protocol (PTP) atau AWS Chrony.

#### 2. Combinatorial Explosion pada Evaluasi OPA Rego
* **Gejala**: Utilisasi CPU OPA melonjak ke 100%, Envoy timeout (504 Gateway Timeout) saat volume request naik.
* **Akar Masalah**: Penggunaan nested loops array comprehension `[x | x := data.rules[_]; x.val == input.val]` tanpa pengindeksan hashmap/dictionary.
* **Solusi**: Refactor aturan Rego agar mengonsumsi data berbasis indexing Key-Value (Lookup `data.roles[input.role]`) yang bekerja pada kompleksitas $\mathcal{O}(1)$ bukan $\mathcal{O}(N^2)$.

#### 3. Kebocoran Socket Descriptor pada High-Concurrency ext_authz
* **Gejala**: Envoy mencatat error: `ext_authz connection error: resource exhaustion` dan me-reject trafik (HTTP 403 / 500).
* **Akar Masalah**: Go gRPC server tidak mengonfigurasi `KeepAlive` parameters dan batas koneksi maksimum, mengakibatkan *TIME_WAIT explosion* pada OS socket stack.
* **Solusi**: Set parameter KeepAlive server pada kode Go:
  ```go
  grpc.KeepaliveParams(keepalive.ServerParameters{
      MaxConnectionIdle: 5 * time.Minute,
      MaxConnectionAge:  30 * time.Minute,
      Time:              1 * time.Minute,
      Timeout:           20 * time.Second,
  })
  ```

---

### 11. Best Practices (Production Checklist)

#### Pre-Flight Deployment Checklist
- [ ] SPIRE Server trust domain tidak menggunakan domain publik yang dapat dispoof.
- [ ] Root signing keys disimpan dalam hardware security module (KMS / HSM) atau di-seal menggunakan Vault transit secrets engine.
- [ ] Masa berlaku sertifikat X.509 SVID ditetapkan antara 10 menit hingga maksimum 1 jam.
- [ ] Node attestation berbasis bukti perangkat keras (AWS IID / Azure MSI / TPM) diaktifkan, bukan join token statis.

#### Runtime & Resilience Checklist
- [ ] Envoy `ext_authz` dikonfigurasi dengan flag `failure_mode_allow: false` (Fail-Closed Architecture) untuk domain keamanan tinggi.
- [ ] Health check probe terpisah dikonfigurasikan pada Envoy dan OPA sidecar; isolasi pod jika daemon OPA gagal beroperasi.
- [ ] Alokasikan resource limits ketat pada container OPA/Envoy: CPU request: 250m, limit: 1000m; Memory request: 128Mi, limit: 512Mi.
- [ ] Audit logging untuk otorisasi ditandai dengan Trace ID (W3C Trace Context) untuk korelasi forensik end-to-end.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/configs
cd hands-on/m02
```

#### Langkah 1: Siapkan SPIRE Server & Agent Minim (Docker Compose)

File: `docker-compose.yaml`
```yaml
version: '3.8'

services:
  spire-server:
    image: ghcr.io/spiffe/spire-server:1.8.0
    container_name: spire-server
    hostname: spire-server
    volumes:
      - ./configs/spire-server.conf:/opt/spire/conf/server/server.conf
    command: ["-config", "/opt/spire/conf/server/server.conf"]
    ports:
      - "8081:8081"

  spire-agent:
    image: ghcr.io/spiffe/spire-agent:1.8.0
    container_name: spire-agent
    depends_on:
      - spire-server
    volumes:
      - ./configs/spire-agent.conf:/opt/spire/conf/agent/agent.conf
      - /var/run:/var/run:rw
    command: ["-config", "/opt/spire/conf/agent/agent.conf"]

  ext-authz-pdp:
    build:
      context: .
      dockerfile: Dockerfile.pdp
    container_name: ext-authz-pdp
    ports:
      - "9001:9001"

  envoy-pep:
    image: envoyproxy/envoy:v1.28.0
    container_name: envoy-pep
    depends_on:
      - ext-authz-pdp
    volumes:
      - ./configs/envoy-config.yaml:/etc/envoy/envoy.yaml
    ports:
      - "8443:8443"
```

#### Langkah 2: Konfigurasi SPIRE Server & Agent

File: `configs/spire-server.conf`
```hcl
server {
    bind_address = "0.0.0.0"
    bind_port = "8081"
    trust_domain = "zero-trust.fde"
    data_dir = "/opt/spire/data/server"
    log_level = "DEBUG"
    ca_ttl = "24h"
    default_x509_svid_ttl = "1h"
}

plugins {
    DataStore "sql" {
        plugin_data {
            database_type = "sqlite3"
            connection_string = "/opt/spire/data/server/datastore.sqlite3"
        }
    }
    NodeAttestor "join_token" {
        plugin_data {}
    }
    KeyManager "disk" {
        plugin_data {
            keys_path = "/opt/spire/data/server/keys.json"
        }
    }
}
```

File: `configs/spire-agent.conf`
```hcl
agent {
    data_dir = "/opt/spire/data/agent"
    log_level = "DEBUG"
    server_address = "spire-server"
    server_port = "8081"
    socket_path = "/var/run/spire/sockets/agent.sock"
    trust_domain = "zero-trust.fde"
}

plugins {
    NodeAttestor "join_token" {
        plugin_data {}
    }
    KeyManager "disk" {
        plugin_data {
            directory = "/opt/spire/data/agent"
        }
    }
    WorkloadAttestor "unix" {
        plugin_data {}
    }
}
```

#### Langkah 3: Eksekusi Bootstrap & Registrasi Workload

Jalankan perintah berikut pada terminal:

```bash
# 1. Start containers
docker compose up -d spire-server

# 2. Generate join token untuk Node Attestation
JOIN_TOKEN=$(docker exec spire-server /opt/spire/bin/spire-server token generate -spiffeID spiffe://zero-trust.fde/node/node01 | awk '{print $2}')

# 3. Masukkan join token ke spire-agent runtime
docker compose up -d spire-agent
docker exec spire-agent /opt/spire/bin/spire-agent run -config /opt/spire/conf/agent/agent.conf -joinToken $JOIN_TOKEN &

# 4. Daftarkan SPIFFE ID untuk Envoy PEP Workload
docker exec spire-server /opt/spire/bin/spire-server entry create \
    -parentID spiffe://zero-trust.fde/node/node01 \
    -spiffeID spiffe://zero-trust.fde/workload/envoy-pep \
    -selector unix:uid:0

# 5. Jalankan full stack (Envoy + PDP)
docker compose up -d ext-authz-pdp envoy-pep

# 6. Validasi Workload API menerima X.509 SVID
docker exec spire-agent /opt/spire/bin/spire-agent api fetch x509 -socketPath /var/run/spire/sockets/agent.sock
```

---

### 13. Exercise

#### Level: Easy
Implementasikan Rego policy pada OPA standalone yang memvalidasi integritas request HTTP:
* Request method harus salah satu dari: `GET`, `POST`, `PUT`.
* Header `X-Correlation-ID` wajib ada dan memiliki panjang minimal 16 karakter.
* Output: `allow = true` jika semua syarat terpenuhi.

#### Level: Medium
Modifikasi file Go `cmd/authz-server/main.go` pada praktikum:
Tambahkan cache in-memory berbasis LRU untuk menampung hasil verifikasi token JWT selama 60 detik. Pastikan penanganan thread-safe menggunakan `sync.RWMutex` dan invalidasi cache otomatis berjalan jika token memasuki masa expired.

#### Level: Hard
Kembangkan program CLI berbasis Go (`spiffe-jwt-injector`) yang:
1. Melakukan dial ke UNIX Domain Socket SPIRE Agent Workload API.
2. Mengambil JWT-SVID untuk audiens target `spiffe://zero-trust.fde/workload/database`.
3. Membuka koneksi TLS ke listener Envoy PEP, menginjeksikan JWT-SVID tersebut ke header `Authorization: Bearer <JWT>`, dan menangani *graceful re-authentication* secara otomatis 30 detik sebelum token kadaluarsa.

---

### 14. Challenge

#### Skenario: "Operation Cross-Domain Mesh Failure"
Anda diutus sebagai Lead FDE ke sebuah konsorsium bank multinasional. Klien mengoperasikan dua cluster OpenShift yang terpisah secara fisik di Swiss dan Singapura.
* **Kondisi**:
  1. Koneksi WAN antar-datacenter memiliki packet loss intermiten 2-5%.
  2. Regulasi Finma (Swiss) melarang private keys atau root certificates keluar dari batas teritorial fisik negara Swiss.
  3. Layanan transaksi di cluster Singapura harus memanggil internal Settlement Service di Swiss menggunakan Zero Trust mTLS architecture.
* **Misi Arsitektur**:
  1. Rancang arsitektur SPIFFE/SPIRE Multi-Trust-Domain Federation yang menjamin kedua cluster saling mengenali SVID tanpa saling mengekspos root private keys.
  2. Susun skema mitigasi ketika WAN terputus: bagaimana pod di Singapura tetap dapat beroperasi untuk request lokal, dan mekanisme fail-closed apa yang menjamin transaksi antar-negara tidak bocor saat jaringan kembali terhubung?
  3. Buat rancangan cetak biru (blueprint) dokumen teknis yang mencakup: Topology Diagram, Rencana Rotasi Trust Bundle, dan Analisis Risiko Kriptografis.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual)
1. **Apa fungsi mendasar dari konsep SVID dalam spesifikasi SPIFFE?**
   * *Jawaban*: SVID (SPIFFE Verifiable Identity Document) berfungsi sebagai dokumen identitas kriptografis portabel (berupa sertifikat X.509 atau JWT) yang membuktikan identitas suatu workload kepada pihak lain dalam trust domain.
2. **Mengapa Zero Trust melarang validasi hak akses hanya berbasis IP Address sumber?**
   * *Jawaban*: Alamat IP bersifat efemeral di lingkungan modern (container/cloud), rentan terhadap teknik IP spoofing, routing poisoning, dan tidak menyediakan jaminan kriptografis mengenai integritas proses/biner yang memicu koneksi tersebut.
3. **Komponen manakah dalam arsitektur NIST SP 800-207 yang direpresentasikan oleh Envoy Proxy?**
   * *Jawaban*: Policy Enforcement Point (PEP).
4. **Apa bahaya mengonfigurasi `failure_mode_allow: true` pada filter `ext_authz` Envoy di lingkungan produksi?**
   * *Jawaban*: Jika authorization engine (PDP) crash, offline, atau mengalami timeout, Envoy akan meloloskan seluruh trafik tanpa otorisasi, menyebabkan insiden keamanan *complete authentication bypass*.
5. **Bagaimana SPIRE Agent memvalidasi identitas pod tanpa meminta password dari pod tersebut?**
   * *Jawaban*: Melalui proses Workload Attestation, di mana agent menginterogasi kernel host Linux via unix domain socket untuk membaca atribut level OS (PID, UID, cgroups, metadata container).

#### Bagian 2: Intermediate (Analisis Arsitektur)
6. **Jelaskan perbedaan mendasar antara X.509-SVID dan JWT-SVID, serta kapan seorang FDE memilih salah satunya!**
   * *Jawaban*: X.509-SVID diterapkan pada layer transport (L4/L7 mTLS), sangat efisien untuk koneksi langsung antar-service, dan aman karena private key tidak pernah ditransmisikan. JWT-SVID diterapkan pada layer aplikasi (L7 HTTP header), cocok ketika request harus melalui multi-hop proxy/L7 load balancer yang melakukan TLS termination.
7. **Dalam integrasi RFC 8693 (Token Exchange), apa peran parameter `actor_token` vs `subject_token`?**
   * *Jawaban*: `subject_token` merepresentasikan identitas entitas utama yang hak aksesnya sedang dipinjam/didelegasikan, sedangkan `actor_token` merepresentasikan identitas sistem perantara (aktor) yang sedang bertindak atas nama entitas subjek tersebut.
8. **Bagaimana cara mencegah memory leak pada Envoy Proxy saat menerima jutaan sertifikat mTLS unik dari klien yang berbeda?**
   * *Jawaban*: Mengaktifkan session ticket caching limits, membatasi ukuran trust store CA, menerapkan filtering SAN validation di level TLS handshake, dan memastikan Envoy membuang SSL sessions yang expired secara periodik via setting `session_timeout`.
9. **Mengapa OPA Rego policy harus dikompilasi ke WebAssembly (Wasm) untuk skenario ultra-low latency?**
   * *Jawaban*: Wasm meniadakan parsing AST dan evaluasi dinamis bahasa Rego tingkat tinggi, mengeksekusi logika biner secara deterministik dan native di dalam thread runtime Envoy/Go, mengurangi *garbage collection pauses*.
10. **Apa strategi paling efektif menangani rotasi CA Root SPIRE tanpa menyebabkan downtime mTLS global?**
    * *Jawaban*: Menjalankan rotasi secara bertahap (*multi-phase rolling update*): 1) Terbitkan Root CA baru; 2) Gabungkan Root CA baru ke dalam Trust Bundle bersama Root CA lama (Dual-Bundle Phase); 3) Mulai terbitkan SVID menggunakan Intermediate/Root baru; 4) Hapus Root CA lama setelah seluruh SVID lama expired.

#### Bagian 3: Skenario Kasus Produksi (Troubleshooting Lapangan)

##### Skenario Kasus 1: "The Intermittent Auth-Storm"
* **Kondisi**: Pada sebuah cluster perbankan, setiap jam 00:00 UTC terjadi lonjakan error `HTTP 401 Unauthorized` serentak selama 2 menit di seluruh armada microservice, kemudian pulih dengan sendirinya.
* **Investigasi**:
  1. SVID TTL di-set selama 1 jam.
  2. Seluruh pod di-deploy serentak menggunakan Helm pada waktu yang sama sehari sebelumnya.
  3. SPIRE Server mengalami beban request puncak (CPU 100%) tepat pada menit ke-00.
* **Pertanyaan**: Apa akar masalah teknisnya dan bagaimana FDE menyelesaikannya?
* **Solusi FDE**:
  * *Akar Masalah*: **Thundering Herd Problem** pada SPIRE Agent renewal cycle. Karena seluruh SVID di-issue pada detik yang sama dan memiliki masa kadaluarsa identik, seluruh agent merequest rotasi SVID pada jendela waktu yang tepat bersamaan, membuat SPIRE Server kewalahan dan gagal merespons SDS request tepat waktu.
  * *Penyelesaian*: Terapkan *jitter/randomized backoff* pada interval rotasi SPIRE Agent (misal: SVID direnew secara acak antara 50% hingga 80% masa hidupnya) sehingga kurva load terdistribusi merata (flatten the curve).

##### Skenario Kasus 2: "The Ghost Workload"
* **Kondisi**: Sebuah container yang dideploy penyerang berhasil mendapatkan SPIFFE ID valid `spiffe://zero-trust.fde/workload/payment-processor` padahal pod tersebut bukan aplikasi payment resmi.
* **Investigasi**:
  1. Workload Attestor pada SPIRE Agent dikonfigurasi dengan selector: `k8s:pod-label:app=payment`.
  2. Penyerang memiliki izin deploy di namespace `dev` dan membuat pod dengan label `app=payment`.
* **Pertanyaan**: Di mana letak kelemahan konfigurasi tersebut dan bagaimana memperbaikinya ke standar enterprise?
* **Solusi FDE**:
  * *Akar Masalah*: Bergantung semata-mata pada selector label Kubernetes (`k8s:pod-label`) adalah fatal, karena label Kubernetes adalah metadata yang tidak terotentikasi dan mudah dipalsukan oleh pengguna yang memiliki akses create pod.
  * *Penyelesaian*: Ubah aturan selector attestation menjadi immutable primitives: gabungkan selector Namespace, ServiceAccount kriptografis, dan Image SHA:
    ```hcl
    # Registrasi Baru yang Aman
    -selector k8s:ns:production-payments
    -selector k8s:sa:payment-processor-sa
    -selector k8s:container-image:internal-registry.bank.com/payment:v2.1.0@sha256:7f83...
    ```

##### Skenario Kasus 3: "The Silent Data Tampering"
* **Kondisi**: Audit menemukan bahwa sebuah microservice analytics yang terisolasi di dalam VPC internal dapat membaca data sensitif kartu kredit dari core banking service, meskipun kebijakan firewall network security groups sudah memblokir port tersebut.
* **Investigasi**:
  1. Jaringan menggunakan shared Envoy Gateway Ingress.
  2. Microservice analytics mengirimkan header `X-Forwarded-For` palsu dan JWT token expired yang tidak divalidasi oleh backend karena backend menganggap validasi sudah dilakukan di Ingress.
* **Pertanyaan**: Mengapa arsitektur ini gagal menerapkan Zero Trust dan bagaimana remedi totalnya?
* **Solusi FDE**:
  * *Akar Masalah*: Terjadi pelanggaran prinsip *Never Trust, Always Verify*. Arsitektur menerapkan *Perimeter Assumption* di mana backend mempercayai upstream proxy secara buta (*Blind Trust*) tanpa memvalidasi cryptographic identity pengirim asli pada setiap hop (*Hop-by-Hop verification failure*).
  * *Penyelesaian*:
    1. Terapkan mTLS ketat hingga titik terminal backend (End-to-End mTLS with SPIFFE SAN parsing di backend Envoy sidecar).
    2. Envoy sidecar backend wajib menolak header `X-Forwarded-*` kecuali berasal dari trusted internal proxies via SAN whitelist.
    3. Eksekusi PDP lokal di level pod backend untuk memvalidasi JWT signature secara lokal, meniadakan ketergantungan pada ingress gateway.

---

### 16. Summary

1. **Zero Trust Bukan Produk, Melainkan Paradigma**: Zero Trust Architecture (NIST SP 800-207) meniadakan konsep zona jaringan terpercaya. Setiap transaksi dikontrol pada level L7 dengan verifikasi identitas, konteks, dan kebijakan yang eksplisit.
2. **Identitas Beban Kerja Dekouple dari Jaringan**: Menggunakan standar terbuka SPIFFE/SPIRE, FDE membebaskan sistem dari ketergantungan IP whitelisting dan static API tokens, menuntaskan problem *Secret Zero* via hardware/OS attestation.
3. **Pemisahan PEP dan PDP Mutlak Diperlukan**: Mengawinkan Envoy Proxy (PEP) berperforma tinggi dengan mesin kebijakan deklaratif Open Policy Agent (PDP) memungkinkan penegakan otorisasi terpusat secara konsisten tanpa mengorbankan latensi mikrodetik.
4. **Resiliensi dan Observabilitas Kriptografis**: Implementasi Zero Trust tingkat enterprise mewajibkan perencanaan matang terkait *clock synchronization*, mitigasi *thundering herd* pada pembaharuan sertifikat, serta audit logging berbasis *cryptographically bound identities*.