# Kurikulum Enterprise: Code Review untuk Sistem Skala Besar
## Kategori: 06-Architecture-and-System-Design
### BAB-05: Review Keamanan & Sanitasi Data
### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Engineer, Software Architect, dan Lead Developer diharapkan mampu:

1. **Menganalisis dan Memetakan Aliran Data Tercemar (*Taint Propagation*)**: Mengidentifikasi titik masuk data tidak terpercaya (*Source*), jalur propagasi (*Pass-through*), dan titik eksekusi berbahaya (*Sink*) secara deterministik pada Pull Request (PR) tingkat lanjut.
2. **Mengevaluasi Keabsahan Sanitasi dan Validasi Kontekstual**: Membedakan antara validasi struktural (skema, tipe) dan sanitasi kontekstual (*context-aware encoding/escaping*) untuk mencegah SQLi, Blind SSRF, RCE, Stored XSS, dan *Insecure Deserialization*.
3. **Mengotomatisasi Pemeriksaan Keamanan Shift-Left pada CI/CD Pipeline**: Mengintegrasikan *Custom Static Application Security Testing* (SAST) berbasis *Abstract Syntax Tree* (AST) dan *Policy-as-Code* (OPA/Rego) guna memblokir antipattern keamanan sebelum kode menyentuh *main branch*.
4. **Mendeteksi Kerentanan Akses Tingkat Arsitektur**: Mengaudit dan menggagalkan celah *Broken Object Level Authorization* (BOLA/IDOR), eskalasi privilese, serta kebocoran batas multi-penyewa (*multi-tenant boundary leak*) dalam kode logika bisnis mikroservis.
5. **Menilai Dampak Performa Mekanisme Sanitasi**: Mengkalkulasi *overhead* latensi, alokasi memori (*heap churn*), dan risiko *Regular Expression Denial of Service* (ReDoS) yang timbul dari implementasi sanitasi data defensif.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:

* **Sistem & Jaringan Komputer**: Pemahaman mendalam tentang Model OSI, TCP/IP handshake, DNS resolution (termasuk DNS Rebinding), protokol HTTP/1.1 dan HTTP/2, serta format payload binary (gRPC/Protobuf) dan tekstual (JSON, XML).
* **Konsep Desain Arsitektur Modern**: Pengalaman merancang microservices, event-driven architecture, API Gateway pattern, Zero-Trust Architecture, dan Identity & Access Management (IAM/OAuth2/OIDC).
* **Security Engineering Fundamental**: Pemahaman komprehensif mengenai *OWASP Top 10 API Security Risks*, *CWE/SANS Top 25 Most Dangerous Software Errors*, dan model ancaman *STRIDE*.
* **Bahasa Pemrograman**: Kemampuan membaca dan menulis kode idiomatik setara *production grade* pada minimal dua bahasa berikut: Go, TypeScript (Node.js runtime), atau Java.

---

### 3. Concept & Internal Architecture (Mendalam)

Review keamanan pada tingkat kode (*code review*) menuntut pemahaman mendalam tentang bagaimana *compiler* dan *runtime engine* memperlakukan data serta instruksi. Mayoritas kerentanan injeksi terjadi akibat **hilangnya pemisahan antara bidang kendali (*control plane*) dan bidang data (*data plane*)**.

#### 3.1 Teori Taint Analysis (Analisis Aliran Data Tercemar)

Secara matematis, keamanan aliran data dapat dimodelkan sebagai *Directed Graph* $G = (V, E)$, di mana:
* Node $V$ terdiri dari himpunan $S$ (*Sources*), $T$ (*Sanitizers/Transformers*), $N$ (*Neutral nodes*), dan $K$ (*Sinks*).
* Edge $E \subseteq V \times V$ memetakan transfer data atau pengaruh kendali antar-instruksi.

```
       [SOURCE] (Untrusted Input)
          │  e.g. req.Header, req.Body, URL Params
          ▼
     [PROPAGATION]
          │  Variable assignment, String concatenation, Struct mapping
          ▼
   ┌──────────────┐
   │ SANITIZER /  │ ──(Invalid/Malicious)──► [REJECT / ABORT]
   │ VALIDATOR    │
   └──────────────┘
          │ (Contextually Encoded / Canonicalized)
          ▼
        [SINK] (Dangerous Execution Context)
             e.g. db.Exec(), os.Exec(), http.Get(), template.HTML()
```

Sebuah kerentanan didefinisikan jika terdapat jalur terarah (*directed path*) dari $s \in S$ ke $k \in K$ tanpa melewati $t \in T$ yang secara formal membuktikan invarian keamanan untuk konteks operasional $k$.

* **Lexical vs AST vs Control Flow Graph (CFG)**:
  * *Lexical Review* (Regex/Grepping): Mencari string seperti `password`, `eval()`, atau `SELECT * FROM`. Pendekatan ini rentan terhadap *false positive* tinggi dan tidak memahami *scoping*.
  * *AST Analysis*: Mengurai kode menjadi pohon sintaks. Memungkinkan reviewer (atau perkakas review otomatis) memverifikasi apakah pemanggilan fungsi berbahaya menggunakan argumen konstan atau variabel dinamis.
  * *CFG & SSA (Single Static Assignment)*: Melacak nilai variabel dari inisialisasi hingga dereferensi melintasi percabangan logika (*branching*) dan pemanggilan fungsi antar-modul (*inter-procedural analysis*). Reviewer kelas enterprise harus mampu melakukan inferensi CFG mental saat membaca PR.

#### 3.2 Canonicalization vs Validation vs Sanitization

Kesalahan paling umum dalam PR adalah pencampuran konsep sanitasi:
1. **Canonicalization (Kanonikalitas)**: Proses mereduksi berbagai representasi data yang ekuivalen ke dalam satu bentuk tunggal standar sebelum evaluasi (misalnya: konversi `%2e%2e%2f` menjadi `../`, pembersihan unicode homoglyphs, atau absolutisasi path file). Validasi yang dilakukan sebelum kanonikalitas adalah cacat desain fatal (*canonicalization bypass*).
2. **Validation (Validasi)**: Menentukan apakah data input mematuhi kontrak tipe, batas rentang (*range*), panjang (*length*), dan *allowlist character set*. Validasi bersifat deterministik: data valid diterima, data tidak valid ditolak langsung (*fail-fast*).
3. **Sanitization/Encoding (Sanitasi)**: Mengubah data yang berpotensi membahayakan menjadi bentuk yang aman untuk interpreter target tertentu (*output encoding*). Sanitasi bersifat *context-dependent*: enkoder HTML Entity tidak akan melindungi sistem jika input ditempatkan ke dalam atribut `href="javascript:..."` atau sub-shell Linux.

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Tradisional) | Pendekatan Enterprise Architecture |
| :--- | :--- | :--- |
| **Fokus Review** | "Apakah sintaks sanitasi ada?" (misal: cek `escapeHTML`) | "Apakah *trust boundary* terlanggar dan apakah konteks sink sesuai dengan tipe enkoder?" |
| **Metode Deteksi** | Regex linter, manual eye-balling sekilas | AST custom analysis, SSA taint tracking, integrasi verification policy via OPA |
| **Penanganan Input** | Blacklisting (memblokir karakter `'`, `"`, `<script>`) | Whitelisting ketat, skema deklaratif, strongly-typed domain primitives |
| **Otorisasi Data** | RBAC global statis pada level router | ABAC fine-grained, contextual object-level check (BOLA mitigation) di domain layer |
| **Siklus Hidup** | Keamanan diuji menjelang rilis (QA/Pentest) | Shift-Left Security: Gate otomatis pada pre-commit, PR validation, dan branch protection |

#### Mengapa Review Tingkat Kode Mutlak Diperlukan?
Mekanisme pertahanan perimeter seperti Web Application Firewall (WAF) hanya bertindak sebagai mitigasi sementara (*compensating control*). WAF tidak memiliki konteks semantik aplikasi, dapat dilewati (*bypassed*) menggunakan payload encoding berlapis, dan tidak dapat menginspeksi data terenkripsi *end-to-end* antar-mikroservis internal (Zero Trust internal boundary).

---

### 5. How (Workflow Detail)

Alur kerja review keamanan modern menerapkan strategi berlapis:

```
[ Developer Local ]
   │
   ├── 1. Pre-commit Hook: Secret scanning (TruffleHog, Gitleaks)
   │
[ Pull Request Created ]
   │
   ├── 2. CI Automation (Static Analysis Gate)
   │     ├─ Semantic AST Analysis (Semgrep ruleset)
   │     ├─ Software Composition Analysis / SCA (Trivy, Snyk)
   │     └─ Policy-as-Code check (OPA / Conftest for infrastructure code)
   │
   ├── 3. Peer Security Code Review (Human Principal/Security Champion)
   │     ├─ Verifikasi Sink & Source
   │     ├─ Pemeriksaan Contextual Canonicalization
   │     ├─ Validasi Boundary Multi-tenancy & IDOR
   │     └─ Evaluasi Kompleksitas Algoritma Sanitizer (ReDoS risk)
   │
   ├── 4. Dynamic Sandbox Verification (Ephemeral Env)
   │     └─ IAST (Interactive Application Security Testing) & DAST Smoke Run
   │
[ Merged to Main ]
```

#### Protokol Reviewer saat Menginspeksi PR Berisiko Tinggi:
1. **Identifikasi Sink Kritis**: Scan perubahan kode untuk menemukan pemanggilan API tingkat rendah (`exec.Command`, `rawQuery`, `sendRedirect`, `unserialize`, `eval`, `html/template`).
2. **Backtrack ke Source**: Tarik alur variabel input dari sink mundur hingga titik injeksi publik (REST controller, GraphQL resolver, Kafka consumer).
3. **Audit Modul Transformasi**: Pastikan parsing dilakukan via *strict schema parser* (Zod, Pydantic, Protobuf) dengan aturan `unknownProperties: deny` / `stripUnknown`.
4. **Validasi Otorisasi Objek**: Pastikan eksekusi sink mengikat *tenant_id* atau *user_id* dari *Cryptographic Context Session*, bukan dari payload request yang dikirimkan klien.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengolahan Air Minum Kota
Bayangkan sistem air minum kota. Air baku diambil dari sungai umum (**Source: Untrusted Input**). 
* **Validation**: Kisi filter memeriksa ukuran objek; batang kayu dan sampah padat langsung ditolak masuk ke intake.
* **Canonicalization**: Air distandardisasi tekanannya dan dialirkan melalui pipa sedimentasi tunggal agar kekeruhannya konsisten.
* **Sanitization**: Klorin dan radiasi UV ditambahkan secara terukur untuk membunuh patogen mikroskopis tanpa meracuni air itu sendiri.
* **Sink (Kran Konsumen)**: Jika sistem langsung memompa air sungai ke kran rumah tangga hanya karena "terlihat bening" (validasi regex primitif), seluruh populasi dapat teracuni saat air tersebut mengandung kontaminan terlarut.

```
       UNTRUSTED ENVIRONMENT (Internet/Client Payload)
  ─────────────────────────────────────────────────────────────
                             │
                             ▼
  ┌───────────────────────────────────────────────────────────┐
  │ [SOURCE] Ingestion Interface (API Gateway / Controller)    │
  └──────────────────────────┬────────────────────────────────┘
                             │ Raw Payload (Tainted: 🔴)
                             ▼
  ┌───────────────────────────────────────────────────────────┐
  │ [TRANSFORMATION 1] Deserialization & Structural Validation│
  │   - Reject unknown properties                             │
  │   - Fail-fast schema matching                             │
  └──────────────────────────┬────────────────────────────────┘
                             │ Parsed Struct (Tainted: 🔴)
                             ▼
  ┌───────────────────────────────────────────────────────────┐
  │ [TRANSFORMATION 2] Canonicalization                       │
  │   - URL Decoding, UTF-8 normalization (NFC/NFKC)          │
  │   - Path canonicalization (filepath.Clean)                │
  └──────────────────────────┬────────────────────────────────┘
                             │ Canonical Form (Tainted: 🔴)
                             ▼
  ┌───────────────────────────────────────────────────────────┐
  │ [TRANSFORMATION 3] Contextual Sanitization & Neutralizer  │
  │   - Prepared Statement Parameterization                   │
  │   - Context-Aware Safe Encoders                           │
  │   - Private IP/Loopback Address Blacklisting (SSRF Guard) │
  └──────────────────────────┬────────────────────────────────┘
                             │ Sanitized / Pure Data (Clean: 🟢)
                             ▼
  ┌───────────────────────────────────────────────────────────┐
  │ [SINK] Execution Operations                               │
  │   - SQL Engine: db.QueryRowContext()                      │
  │   - File System: os.OpenFile() (Secured Sandbox)          │
  │   - Internal Network: http.Client (Secured DialContext)   │
  └───────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example (Pemisahan SQL Data vs Control Plane)

**Vulnerable Pattern (PR ditolak):**
```go
// Reviewer Note: Fatal injection. String formatting allows raw SQL manipulation.
func GetUserTransactions(db *sql.DB, tenantID, accountID string) (*sql.Rows, error) {
    query := fmt.Sprintf("SELECT id, amount FROM txs WHERE tenant_id = '%s' AND account_id = '%s'", tenantID, accountID)
    return db.Query(query)
}
```

**Enterprise Fixed Pattern (Approved):**
```go
// Reviewer Note: Query parameterization binds variables strictly to the data plane.
func GetUserTransactions(ctx context.Context, db *sql.DB, tenantID, accountID string) (*sql.Rows, error) {
    const query = `
        SELECT id, amount 
        FROM txs 
        WHERE tenant_id = $1 AND account_id = $2
    `
    return db.QueryContext(ctx, query, tenantID, accountID)
}
```

---

#### 7.2 Practical Example (Industrial Grade): SSRF & Path Traversal Defensive Proxy

Skenario: Microservice menerima permintaan untuk mengunduh avatar eksternal dari URL yang ditentukan pengguna dan menyimpannya ke disk lokal.

**Implementasi Aman Produksi (Go):**

```go
package security

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

var (
	ErrUnsafeDestination = errors.New("security: destination IP falls into restricted range")
	ErrInvalidPath        = errors.New("security: traversal detected or path outside base directory")
	ErrPayloadTooLarge    = errors.New("security: payload exceeds maximum allowable threshold")
)

type SecureImageFetcher struct {
	baseStorageDir string
	httpClient     *http.Client
	maxBytes       int64
}

func NewSecureImageFetcher(storageDir string, maxBytes int64) (*SecureImageFetcher, error) {
	cleanBase, err := filepath.Abs(storageDir)
	if err != nil {
		return nil, fmt.Errorf("failed to canonicalize base directory: %w", err)
	}

	// Custom transport with strict DNS and Socket Control to mitigate SSRF and DNS Rebinding
	dialer := &net.Dialer{
		Timeout:   3 * time.Second,
		KeepAlive: 30 * time.Second,
		Control: func(network, address string, c syscall.RawConn) error {
			host, _, err := net.SplitHostPort(address)
			if err != nil {
				return err
			}
			ip := net.ParseIP(host)
			if ip == nil {
				return ErrUnsafeDestination
			}
			if isRestrictedIP(ip) {
				return ErrUnsafeDestination
			}
			return nil
		},
	}

	transport := &http.Transport{
		DialContext:           dialer.DialContext,
		ResponseHeaderTimeout: 5 * time.Second,
		TLSHandshakeTimeout:   3 * time.Second,
		DisableKeepAlives:     true, // Prevent connection reuse attacks
	}

	return &SecureImageFetcher{
		baseStorageDir: cleanBase,
		httpClient: &http.Client{
			Transport: transport,
			Timeout:   10 * time.Second,
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				// Prevent blind open redirects bypassing DNS rebinding verification
				return http.ErrUseLastResponse
			},
		},
		maxBytes: maxBytes,
	}, nil
}

// isRestrictedIP checks for loopback, private RFC1918, RFC4193, link-local, and multicast
func isRestrictedIP(ip net.IP) bool {
	if ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() || ip.IsUnspecified() {
		return true
	}
	// Defend against Cloud Metadata Services (e.g. AWS 169.254.169.254)
	if ip.Equal(net.ParseIP("169.254.169.254")) {
		return true
	}
	return false
}

// FetchAndStore securely canonicalizes file paths and pulls data avoiding SSRF
func (s *SecureImageFetcher) FetchAndStore(ctx context.Context, targetURL, rawFileName string) (string, error) {
	// 1. URL Canonicalization & Scheme Validation
	parsedURL, err := url.ParseRequestURI(targetURL)
	if err != nil {
		return "", fmt.Errorf("malformed URL: %w", err)
	}
	if parsedURL.Scheme != "https" { // Enforce TLS-only in production
		return "", errors.New("unsupported protocol scheme: HTTPS is strictly required")
	}

	// 2. Strict Path Traversal Mitigation (Canonicalization + Boundary Check)
	cleanedFilename := filepath.Base(filepath.Clean(rawFileName))
	destinationPath := filepath.Join(s.baseStorageDir, cleanedFilename)

	// Ensure destination remains strictly inside baseStorageDir
	rel, err := filepath.Rel(s.baseStorageDir, destinationPath)
	if err != nil || strings.HasPrefix(rel, "..") {
		return "", ErrInvalidPath
	}

	// 3. Execution Phase via Hardened Client (Guards against SSRF & TOCTOU DNS Rebinding)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, parsedURL.String(), nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", "SecureEnterpriseFetcher/2.0")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("egress request aborted: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("unexpected upstream status: %d", resp.StatusCode)
	}

	// 4. Ingestion Mitigation: Bounded Reader (Prevent Memory/Disk Exhaustion DoS)
	fileTarget, err := os.OpenFile(destinationPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0600)
	if err != nil {
		return "", fmt.Errorf("failed to initialize destination: %w", err)
	}
	defer fileTarget.Close()

	limitedReader := io.LimitReader(resp.Body, s.maxBytes+1)
	written, err := io.Copy(fileTarget, limitedReader)
	if err != nil {
		_ = os.Remove(destinationPath)
		return "", fmt.Errorf("stream copy failed: %w", err)
	}

	if written > s.maxBytes {
		_ = os.Remove(destinationPath)
		return "", ErrPayloadTooLarge
	}

	return destinationPath, nil
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Pelanggaran Batas Multi-Tenant & SSRF FinTech Mega-App
* **Latar Belakang**: Sebuah platform Core Banking Microservices dengan throughput >50.000 TPS memperbarui layanan *Webhook Dispatcher*.
* **Cacat Kode pada Pull Request**:
  PR mengimplementasikan pengiriman data transaksi ke endpoint custom klien menggunakan `http.DefaultClient`. Untuk optimasi performa, developer mengizinkan klien mendaftarkan URL webhook mereka secara langsung melalui API.
* **Vektor Serangan Terabaikan**:
  1. Penyerang mendaftarkan URL webhook: `http://169.254.169.254/latest/meta-data/iam/security-credentials/`.
  2. Ketika transaksi dipicu, webhook worker melakukan `POST` payload ke alamat tersebut. Metadata instance AWS bocor via respon error worker yang dicatat ke sistem observabilitas sentral (Elasticsearch).
  3. Terjadi juga **BOLA (Broken Object Level Authorization)** di endpoint pendaftaran webhook: ID penyewa diambil langsung dari JSON body (`{"tenant_id": "victim-corp"}`) dan bukan dari claims token JWT microservice yang diautentikasi.
* **Dampak Finansial & Regulasi**: Penyerang mampu memalsukan otentikasi AWS IAM peran produksi dan memanipulasi webhook settlement merchant lain, mengakibatkan potensi kerugian settlement senilai $2.4M sebelum dibendung.
* **Penyelesaian Pasca-Insiden via Code Review Standards**:
  * Mandatory Custom Linter: Memblokir penggunaan `http.DefaultClient` dan `http.Get` di seluruh repositori. Wajib menggunakan `EgressSecurityTransport` dengan isolasi subnetwork via forward proxy internal.
  * Structural Code Review Rule: Seluruh `tenant_id` dan `account_id` harus di-inject melalui `middleware.GetTenantFromContext(ctx)`. Seluruh PR yang memparsing `tenant_id` dari payload JSON `POST`/`PUT` langsung ditolak otomatis oleh CI linter.

---

### 9. Trade-offs

| Parameter Desain | Pendekatan Restriktif / Defensif Maksimal | Pendekatan Permisif / Pragmatis | Analisis Trade-off Arsitektur |
| :--- | :--- | :--- | :--- |
| **Parsing Sanitasi Input** | Deep AST Parsing & Recursive Schema Scrubbing | Flat String Scanning & Surface Filtering | **Latensi & CPU Churn**: Deep parsing payload JSON nested 10-level dapat meningkatkan latensi P99 dari 2ms ke 45ms. Wajib membatasi kedalaman deserialization (`MaxDepth`). |
| **Mitigasi SSRF** | Zero Direct Egress, Dedicated Forward Proxy & IP Pinning via Socket Control | Standard `http.Client` dengan Regex Check URL host | **Kompleksitas & Biaya**: IP pinning mematikan HTTP Keep-Alive dan TLS Session Resumption, meningkatkan latensi handshake egress hingga 300%. |
| **Pipeline CI/CD Gates** | Full SSA Taint Analysis & Static Gate (Zero Tolerance Failure) | Linters Cepat + Manual Sample Review | **Developer Velocity**: Analisis SSA inter-procedural membutuhkan waktu 10-25 menit per PR build. Menurunkan frekuensi deployment tim produk. |
| **Kanonikalitas Data** | Strict Unicode Normalization Form C (NFC) & Complete Transcoding | Ingest As-Is dengan Output Sanitization saat Read | **Integritas vs Skalabilitas Write**: Normalisasi string pada write-path membebani CPU, tetapi mengabaikannya berisiko memunculkan bypass otentikasi berbasis homoglyph. |

---

### 10. Common Mistakes & Troubleshooting

#### Antipattern 1: ReDoS (Regular Expression Denial of Service) pada Sanitizer
* **Kode Buruk**:
  ```javascript
  // Reviewer Warning: Catastrophic Backtracking jika string berisi "aaaaaaaaaaaaaaaaaaaaaaaaaaaa!"
  const emailRegex = /^([a-zA-Z0-9_\.\-])+\@(([a-zA-Z0-9\-])+\.)+([a-zA-Z0-9]{2,4})+$/;
  ```
* **Solusi**: Gunakan deterministic finite automata (DFA) regex engines (misal: Go `regexp` yang berbasis RE2) atau gunakan parser berbasis Finite State Machine (FSM), bukan RegEx NFA kompleks.

#### Antipattern 2: Double Encoding / Dual Decoding Vulnerability
* **Skenario Masalah**: WAF memvalidasi data setelah melakukan satu kali `urlDecode`. Namun, service internal melakukan `urlDecode` kedua kalinya di domain logic.
* **Dampak**: Payload `%252e%252e%252f` -> di-decode oleh WAF menjadi `%2e%2e%2f` (dianggap aman dari traversal) -> di-decode oleh aplikasi menjadi `../` (Directory Traversal tereksekusi).
* **Solusi Review**: Pastikan arsitektur hanya mengizinkan *Single Ingestion Decoding Boundary* pada entry layer. Jangan melakukan dekode URL berulang di domain layer.

#### Antipattern 3: Insecure Deserialization via Type Polymorphism
* **Kode Buruk (Java / Jackson)**:
  ```java
  // Reviewer Warning: mengizinkan instansiasi sembarang kelas yang ada di classpath (RCE Gadget Chains)
  objectMapper.enableDefaultTyping(); 
  ```
* **Solusi**: Nonaktifkan polymorph typing bebas. Terapkan allowlist eksplisit (`BasicPolymorphicTypeValidator`) untuk kelas-kelas target DTO.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini saat meninjau (*reviewing*) PR yang memanipulasi data:

#### Author Checklist Sebelum Mengajukan PR:
- [ ] Semua input eksternal dimodelkan menggunakan tipe data terstruktur (DTO strongly-typed), bukan `map[string]interface{}` atau raw dictionary.
- [ ] Validasi data menggunakan pendekatan *Allowlist* (karakter, rentang, skema) bukan *Denylist*.
- [ ] Tidak ada penggunaan konkatenasi string untuk pembentukan kueri database, perintah sistem, atau template HTML.
- [ ] Path manipulasi file lokal telah diverifikasi menggunakan `filepath.Clean` dan dipastikan memiliki awalan (*prefix*) direktori basis yang absolut.
- [ ] Operasi HTTP egress internal memblokir IP rentang loopback, RFC 1918, RFC 4193, dan AWS/GCP/Azure Metadata Endpoint.
- [ ] Konteks keamanan (User Identity, Tenant ID) selalu diambil dari trusted context/session token, bukan dari payload request yang dikirim klien.

#### Reviewer Gate Checklist (PR Approval):
- [ ] Apakah ada dependensi baru yang ditambahkan? Pastikan versi telah di-pin dan lolos audit SCA (*no known CVE*).
- [ ] Jika terdapat regular expression baru: Apakah ekspresi tersebut kebal terhadap *catastrophic backtracking*?
- [ ] Jika endpoint mengekspos data berdasarkan ID: Apakah ada verifikasi bahwa entitas yang diminta merupakan milik organisasi/penyewa pengguna yang sedang aktif?
- [ ] Apakah payload streaming/upload dibatasi kapasitasnya (`LimitReader` / `MaxBodySize`) untuk mencegah denial of service?
- [ ] Apakah log sanitasi data diterapkan? Pastikan PII (Personally Identifiable Information), token bearer, atau password tidak dicatat ke log aplikasi (*log scrubbing*).

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini di direktori: `hands-on/m02/`

#### Langkah 1: Inisialisasi Environment
Buat struktur direktori untuk praktikum pembuatan Custom AST Security Rule:
```bash
mkdir -p hands-on/m02/rules hands-on/m02/src
cd hands-on/m02
```

#### Langkah 2: Buat Kode Rentan untuk Pengujian
Tulis file `hands-on/m02/src/vulnerable_service.go`:
```go
package main

import (
	"database/sql"
	"fmt"
	"net/http"
	"os/exec"
)

func Handler(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	// Source
	userInput := r.URL.Query().Get("cmd")
	tenantID := r.URL.Query().Get("tenant")

	// Vulnerable Sink 1: Command Injection
	cmd := exec.Command("sh", "-c", userInput)
	_ = cmd.Run()

	// Vulnerable Sink 2: SQL Injection
	q := fmt.Sprintf("SELECT * FROM users WHERE tenant = '%s'", tenantID)
	_, _ = db.Query(q)
}
```

#### Langkah 3: Definisikan Custom AST Scanner Rule (Semgrep)
Buat file `hands-on/m02/rules/enterprise_security_rules.yaml`:
```yaml
rules:
  - id: enterprise-raw-sql-injection-gate
    languages: [go]
    message: "FATAL: Ditemukan konkatenasi string dinamis pada pemanggilan SQL Query. Gunakan parameterized query."
    severity: ERROR
    patterns:
      - pattern-either:
          - pattern: $DB.Query(fmt.Sprintf(...), ...)
          - pattern: $DB.Exec(fmt.Sprintf(...), ...)
          - pattern: |
              $QUERY := fmt.Sprintf(...)
              ...
              $DB.Query($QUERY, ...)

  - id: enterprise-command-injection-gate
    languages: [go]
    message: "FATAL: Eksekusi command shell terdeteksi menggunakan input eksternal tanpa allowlist sanitasi."
    severity: ERROR
    patterns:
      - pattern: exec.Command("sh", "-c", $INPUT)
      - pattern-not: exec.Command("sh", "-c", "...")
```

#### Langkah 4: Eksekusi Pengujian Audit Keamanan
Jalankan Semgrep berbasis rule kustom yang telah dibuat:
```bash
# Jalankan via Semgrep Docker jika local binary belum terpasang
docker run --rm -v "${PWD}:/src" returntocorp/semgrep semgrep \
  --config=/src/rules/enterprise_security_rules.yaml /src/src
```

#### Langkah 5: Evaluasi Output Linting
Verifikasi bahwa automated gate mendeteksi kedua kerentanan tersebut secara akurat dengan exit code non-zero, membuktikan mekanisme proteksi PR gate bekerja.

---

### 13. Exercise

#### Level: Easy
Diberikan cuplikan kode Node.js Express berikut:
```javascript
app.get('/download', (req, res) => {
    const filename = req.query.file;
    res.sendFile('/var/www/uploads/' + filename);
});
```
*Tugas*: Identifikasi CWE kerentanan tersebut. Tuliskan ulang implementasinya dengan sanitasi path kanonikal yang valid sehingga upaya payload `../../../../etc/passwd` gagal total.

#### Level: Medium
Sebuah endpoint pencarian Elasticsearch internal dibangun menggunakan microservice Go. Pengembang membuat query DSL dengan memanipulasi string JSON:
```go
query := fmt.Sprintf(`{"query": {"match": {"content": "%s"}}}`, req.SearchTerm)
```
*Tugas*: 
1. Tunjukkan bagaimana attacker dapat melakukan *JSON Injection* untuk mengubah logika query (misal: menambahkan filter untuk mencuri data privat).
2. Tuliskan implementasi aman menggunakan native typed builder Go struct yang di-marshal ke JSON secara deterministik.

#### Level: Hard
Rancang arsitektur review berbasis Go middleware untuk memvalidasi dan mengenkripsi payload JSON yang masuk ke 20 microservices downstream:
* Middleware harus membatasi ukuran input (`MaxBytesReader`).
* Memeriksa deep recursion depth (maksimal 5 layer).
* Melakukan sanitasi otomatis karakter non-printable ASCII / UTF-8 invalid.
* Mencegah alokasi heap berlebih (gunakan `sync.Pool` untuk buffer deserialisasi).

---

### 14. Challenge

**Skenario**:
Anda adalah Principal Security Architect di penyedia platform SaaS Enterprise B2B. Tim engineering mengajukan Pull Request sebesar +1.200 baris yang mengimplementasikan sistem kustom *Dynamic Formula Evaluator* untuk modul payroll. Pengguna level tenant admin dapat menulis formula matematika sederhana seperti:
`TOTAL = BASE_SALARY + (HOURS_WORKED * RATE) - DEDUCTIONS`

Namun, mesin interpreter yang digunakan tim adalah runtime script dinamis (misalnya embedded JavaScript V8 engine atau embedded Python interpreter).

**Tantangan**:
1. Lakukan audit arsitektur terhadap pendekatan ini: Apa saja vektor serangan eskalasi privilese, *sandbox escaping*, dan resource exhaustion yang dapat mengeksekusi kode arbitrary pada level kernel/host?
2. Bagaimana Anda menyusun rejection review comment yang profesional, berbasis data, dan menyertakan rekomendasi arsitektur pengganti?
3. Rancang arsitektur alternatif yang aman untuk kebutuhan formula tersebut tanpa menggunakan interpreter script dinamis (misal: penguraian berbasis Abstract Syntax Tree murni menggunakan algoritma Shunting-yard dan Finite State Machine yang hanya mengevaluasi token matematika whitelist).

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Apa perbedaan mendasar antara *Structural Validation* dan *Contextual Output Encoding*?
2. Mengapa pendekatan validasi berbasis *Blacklisting* karakter secara mutlak dilarang dalam arsitektur keamanan produksi?
3. Dalam terminologi *Taint Analysis*, jelaskan apa yang dimaksud dengan *Source* dan berikan 2 contoh konkretnya pada protokol HTTP.
4. Apa ancaman keamanan yang muncul jika fungsi `filepath.Clean()` dijalankan pada path yang belum dikonversi ke path absolut?
5. Mengapa prepared statement / parameterized query pada database client library kebal terhadap serangan SQL Injection konvensional?

#### Intermediate (5 Pertanyaan)
1. Bagaimana penyerang dapat memanfaatkan fenomena *DNS Rebinding* untuk melewati pengecekan IP validasi SSRF, dan bagaimana cara memitigasinya pada layer soket jaringan?
2. Jelaskan konsep *Second-Order SQL Injection* atau *Stored XSS*! Mengapa validasi data pada read-path terkadang masih gagal melindungi sistem jika sanitasi write-path diabaikan?
3. Mengapa parser format data ekspresif seperti XML rentan terhadap serangan XXE (*XML External Entity*), dan konfigurasi parser apa yang wajib diinspeksi oleh reviewer?
4. Bagaimana kerentanan BOLA (*Broken Object Level Authorization*) dapat terjadi pada kode yang sudah memiliki sistem RBAC (*Role-Based Access Control*) global yang aktif?
5. Jelaskan mekanisme *Catastrophic Backtracking* pada regex NFA engine dan sebutkan dua langkah konkrit reviewer untuk mendeteksinya dalam PR!

#### Skenario Kasus Produksi (3 Pertanyaan)

1. **Skenario A**: Dalam sebuah PR e-commerce, developer menulis logika berikut:
   ```python
   # Mengirim konfirmasi invoice ke remote URL klien
   def send_invoice(callback_url, invoice_data):
       parsed = urllib.parse.urlparse(callback_url)
       if parsed.hostname.endswith(".clientdomain.com"):
           requests.post(callback_url, json=invoice_data)
   ```
   Sebagai reviewer, identifikasi minimal **dua kelemahan fatal** dari implementasi validasi URL di atas yang dapat disalahgunakan oleh penyerang!

2. **Skenario B**: Tim engineering mengimplementasikan microservice multi-penyewa (*multi-tenant*). Untuk kemudahan kueri, mereka menggunakan single database schema bersama dengan kolom `tenant_id` di setiap tabel. Saat meninjau PR pada layer repository, Anda melihat pola penulisan:
   ```go
   func (r *Repo) UpdateOrderStatus(ctx context.Context, orderID string, status string) error {
       return r.db.ExecContext(ctx, "UPDATE orders SET status = $1 WHERE id = $2", status, orderID)
   }
   ```
   Jelaskan risiko arsitektural yang terjadi pada potongan kode di atas, dampak bisnisnya, dan tuliskan perbaikan kodenya!

3. **Skenario C**: Pada PR sistem otentikasi Single Sign-On (SSO), pengembang menerapkan verifikasi JWT signature secara manual karena mengklaim library standar "terlalu lambat":
   ```go
   // Parsing header untuk mendapatkan algoritma
   header := decodeHeader(tokenParts[0])
   if header.Alg == "none" {
       // Allow algorithm none for internal development testing
       return parseClaimsUnsafe(tokenParts[1])
   }
   ```
   Jelaskan dampak bencana keamanan dari kode tersebut jika dirilis ke produksi dan buat checklist wajib bagi reviewer yang menangani kode kriptografi/otentikasi!

---

### 16. Summary

1. **Prinsip Dasar Separasi Plane**: Semua kerentanan injeksi (SQLi, Command Injection, XSS) berakar dari tercampurnya batas antara *Control Plane* (instruksi logika eksekusi) dan *Data Plane* (nilai/literal input). Sanitasi dan parameterisasi bertugas mempertahankan batas ini secara absolut.
2. **Kanonikalitas Sebelum Validasi**: Data tidak boleh divalidasi dalam bentuk terenkripsi atau berpotensi multi-representasi. Seluruh payload wajib melalui fase kanonikalitas tunggal sebelum aturan validasi diterapkan.
3. **Kontekstual adalah Kunci**: Tidak ada satu fungsi sanitasi universal yang dapat membersihkan data untuk semua sink. Sanitasi harus spesifik terhadap interpreter tujuan (SQL Parameter Binding, Shell Escaping, HTML Entity Encoding, URL Percent Encoding).
4. **Shift-Left Automation**: Manual code review rentan terhadap kelalaian manusia (*cognitive fatigue*). Arsitektur review modern harus mempercayakan pendeteksian pola sintaks dasar ke perkakas otomatis berbasis AST dan Policy-as-Code (Semgrep, OPA), sehingga reviewer manusia dapat memfokuskan intelektualitasnya pada evaluasi integritas logika bisnis, batas isolasi multi-tenancy, dan model ancaman terdistribusi.