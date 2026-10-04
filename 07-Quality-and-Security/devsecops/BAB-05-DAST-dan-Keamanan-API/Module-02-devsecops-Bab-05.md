# Kurikulum Enterprise DevSecOps: BAB-05 DAST & Keamanan API
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan arsitektur Dynamic Application Security Testing (DAST) terdistribusi dan *ephemeral* pada pipeline CI/CD skala enterprise.
- Mengintegrasikan pengujian keamanan API berbasis stateful fuzzing dan contract-driven security testing menggunakan OpenAPI/Swagger v3 specs.
- Mengotomatisasi penanganan autentikasi kompleks (OAuth2 Proof Key for Code Exchange [PKCE], JWT rotation, multi-tenant session injection, dan mTLS) di dalam dynamic security scanner.
- Membangun mekanisme orkestrasi pemindaian paralel, deduplikasi kerentanan, dan *automated triage* dengan DefectDojo.
- Menerapkan *security quality gates* berbasis metrik Mean Time to Remediate (MTTR), CVSS v3.1/v4.0 scoring threshold, dan zero-false-positive baseline.

---

### 2. Prerequisite
- **DevSecOps Core**: Pemahaman mendalam tentang SAST dan SCA (Module 01 - 04).
- **Network & Protocol**: Penguasaan HTTP/1.1, HTTP/2, WebSockets, TLS 1.3 handshakes, mutual TLS (mTLS), dan REST/GraphQL conventions.
- **Containerization & Orchestration**: Kemahiran mengelola container Docker, Docker Compose, dan Helm Chart pada Kubernetes (EKS/GKE/Private K8s).
- **CI/CD Platform**: Pengalaman tingkat lanjut mengelola runner pipeline (GitLab CI runners atau GitHub Actions self-hosted runners).
- **Scripting & Automation**: Penguasaan Python 3.10+ (library: `requests`, `schemathesis`, `pydantic`) dan Bash scripting.
- **Security Tools Experience**: Pengetahuan operasional OWASP ZAP core engine, curl, dan Burp Suite Suite CLI/REST API.

---

### 3. Concept & Internal Architecture
Dynamic Application Security Testing (DAST) pada tingkat enterprise tidak lagi mengandalkan pemindaian manual berbasis Graphical User Interface (GUI) yang memakan waktu belasan jam. DAST modern beroperasi dalam arsitektur otomatis, non-intrusif, dan berorientasi *black-box/grey-box execution* di mana payload pengujian diinjeksikan langsung ke runtime aplikasi yang sedang berjalan di *ephemeral preview environment*.

```
+---------------------------------------------------------------------------------------------------+
|                                PRODUCTION-GRADE DAST ARCHITECTURE                                 |
+---------------------------------------------------------------------------------------------------+

 [Git Trigger] ---> [CI Pipeline Runner]
                           |
                           +---> 1. Spin-up Isolated Preview Env (K8s Namespace/K3s)
                           |        |--> Target Microservice App (Instrumented with APM)
                           |        +--> Mock Services (MockServer / WireMock for 3rd Parties)
                           |
                           +---> 2. Auth Context Broker (Sidecar/Pre-step)
                           |        |--> Obtains Fresh JWT via OAuth2 Client Credentials / PKCE
                           |        +--> Injects Sessions/Tokens to DAST Engine Vault
                           |
                           +---> 3. Orchestration: Distributed Scanning Engine
                           |        |
                           |        +---> [Contract-Driven API Fuzzer] (Schemathesis / RESTler)
                           |        |        |--> Validates Schema Adherence & HTTP Fault Injections
                           |        |
                           |        +---> [Headless Browser Crawler] (ZAP Automation Engine)
                           |                 |--> Executes DOM XSS, SSRF, Auth Bypass, CORS scans
                           |
                           +---> 4. In-Flight Telemetry & Webhook Interceptor
                           |        |--> Filters 429 (Rate Limits) & 503 (Circuit Breaks)
                           |        +--> Controls Throttle Rates dynamically
                           |
                           +---> 5. Normalization, Deduplication & Quality Gate
                                    |--> Convert ZAP XML/Schemathesis JSON to SARIF / DefectDojo API
                                    +--> Quality Gate: Fail build if CVSS >= 7.0 (High/Critical)
```

#### Komponen Internal Arsitektur:
1. **Target Runtime Orchestrator**: DAST membutuhkan target yang aktif. Arsitektur enterprise mengisolasi target ke dalam *ephemeral namespace* berbasis Kubernetes untuk mencegah data leakage atau *cross-test contamination*.
2. **Authentication Token Broker**: Mengatasi limitasi DAST tradisional yang kerap gagal menembus *authenticated routes*. Token Broker mengeksekusi *pre-flight authentication* dan menyuplai token yang diperbarui secara asinkron ke scanning engine sebelum *access token* kedaluwarsa.
3. **Engine Dualitas (Crawler vs. Contract-Driven Engine)**:
   - *Headless Browser Crawling (Spider)*: Menavigasi dynamic Single Page Applications (SPA) untuk memetakan input-point DOM dan state transitions.
   - *Specification-Driven Fuzzing Engine*: Mem-parsing OpenAPI/Swagger untuk menghasilkan payload state-aware (positive & negative mutation) guna mengungkap broken object-level authorization (BOLA/IDOR), parameter tampering, dan unhandled runtime exceptions.
4. **SARIF Normalizer & DefectDojo Syncer**: Mengonversi output proprietary scanner ke format standar OASIS SARIF (Static Analysis Results Interchange Format) dan mempublikasikannya ke vulnerability management platform via REST API.

---

### 4. Why & What
- **Why**: SAST hanya memeriksa representasi kode statis; ia buta terhadap kelemahan konfigurasi runtime, parsing error pada network interface, TLS downgrade, environment variable misconfiguration, dynamic route injection, dan otentikasi session leak. DAST memvalidasi apakah kerentanan yang terdeteksi di SAST benar-benar *exploitable* secara real-time pada layer network dan HTTP engine.
- **What**: Implementasi modul ini mencakup *end-to-end continuous dynamic testing pipeline* yang menggabungkan:
  - OWASP ZAP Automation Framework (ZAP AF) dalam mode daemon headless.
  - Contract-based API Property Testing menggunakan `Schemathesis`.
  - Integrasi session state automation melalui runtime environment variable extraction.
  - Automated dynamic policy enforcement ke sistem ticketing/issue tracker.

---

### 5. How (Workflow Detail)
Alur eksekusi DAST enterprise dalam CI/CD:
1. **Environment Provisioning**: CI agent melakukan deployment image target ke cluster pengujian lokal/staging.
2. **Schema Ingestion & Validation**: CI mengunduh OpenAPI v3 schema (`openapi.json`), memverifikasi integritas endpoint path, query parameters, dan request body schema.
3. **Authentication Handshake**: DAST Auth Script mengeksekusi request ke Auth0/Keycloak mock atau staging endpoint, mengambil JWT Token, dan menyematkannya ke standard HTTP header (`Authorization: Bearer <token>`).
4. **Passive Scanning Phase**:
   - Menjalankan request eksploratori yang valid berdasarkan schema.
   - Passive scanner menganalisis response HTTP headers (Missing HSTS, Content-Security-Policy, CORS wildcard, Cookie security flags, Information Disclosure).
5. **Active Scanning & Fuzzing Phase**:
   - Schema Mutation Fuzzing (Boundary value analysis, type violation, SQLi/Command Injection payloads).
   - OWASP API Top 10 target checks: Broken Object Level Authorization (BOLA), Broken Object Property Level Authorization (BOPLA), Server-Side Request Forgery (SSRF).
6. **Teardown & Cleanup**: Menghancurkan ephemeral database dan environment untuk mencegah penumpukan resource.
7. **Metric Extraction & Breaking Build**: CI agent mengekstrak SARIF file, membaca jumlah severity issue, dan menetapkan exit-code `1` jika terdapat threshold breach.

---

### 6. Analogy & Diagram ASCII

#### Analogi:
- **SAST** seperti seorang arsitek yang memeriksa cetak biru (*blueprint*) gedung di atas kertas; ia dapat melihat jika ada pilar penopang yang digambar terlalu tipis.
- **DAST** seperti tim penguji ketahanan fisik (*stress-tester*) yang datang langsung ke gedung yang **sudah berdiri**: mereka mengguncang pilar, mencoba mendobrak pintu darurat, mengetes apakah sistem sprinkler menyala ketika ada asap buatan, dan memastikan kartu akses satpam tidak bisa digunakan sembarang orang untuk masuk ke ruang server.

```
                    +--------------------+
                    | Application Target |
                    |  (Online Service)  |
                    +---------+----------+
                              ^
        [HTTP / REST Requests]| [Responses]
                              v
    +----------------------------------------------------+
    |              ZAP Core Engine (Daemon)              |
    |                                                    |
    | +--------------------+      +--------------------+ |
    | |   Spider Engine    | ---> | Active Scan Engine | |
    | |  (Discovers URLs)  |      | (Payload Injection)| |
    | +--------------------+      +--------------------+ |
    |           |                           |            |
    |           +-------------+-------------+            |
    |                         v                          |
    |          +-----------------------------+           |
    |          | Passive Rules (In-flight)   |           |
    |          | - Missing Headers           |           |
    |          | - Cookie Attributes         |           |
    |          +-----------------------------+           |
    +----------------------------------------------------+
                              |
                     [Exports SARIF/JSON]
                              v
    +----------------------------------------------------+
    |         Pipeline Quality Gate Validation           |
    |   Criteria: Critical == 0 && High <= 0 -> PASS     |
    +----------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: ZAP Automation Framework (YAML)
Konfigurasi deklaratif ZAP Automation Framework (`zap.yaml`) untuk memindai OpenAPI schema secara lokal/pipeline sederhana:

```yaml
env:
  contexts:
    - name: "Enterprise-API-Context"
      urls:
        - "http://api-target.internal:8080"
      includePaths:
        - "http://api-target.internal:8080/v1/.*"
      authentication:
        method: "manual"
      sessionManagement:
        method: "headers"
        parameters:
          Authorization: "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummytoken"

jobs:
  - type: openapi
    parameters:
      apiFile: "/zap/wrk/openapi.json"
      targetUrl: "http://api-target.internal:8080"

  - type: passiveScan-wait
    parameters:
      maxDuration: 5

  - type: activeScan
    parameters:
      context: "Enterprise-API-Context"
      maxRuleDurationInMins: 5
      maxScanDurationInMins: 15
      policy: "API-Minimal-Scan-Policy"

  - type: report
    parameters:
      template: "sarif-json"
      reportDir: "/zap/wrk"
      reportFile: "zap-results.sarif"
```

#### 7.2 Practical Example: Enterprise Stateful API Fuzzing Script
Script otomasi berbasis Python menggunakan `schemathesis` dengan custom hook untuk mutasi state autentikasi multi-peran dan validasi error 5xx:

```python
#!/usr/bin/env python3
"""
Enterprise Dynamic API Security Fuzzer
Engine: Schemathesis (OpenAPI 3.x)
Fitur: Automated State-Aware Payload Injection, Header Rotation, dan Defect Logging
"""

import sys
import os
import requests
import schemathesis
from schemathesis.checks import not_a_server_error
from schemathesis.models import Case

TARGET_BASE_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080")
OPENAPI_SPEC_PATH = os.getenv("OPENAPI_SPEC_PATH", "/specs/openapi.json")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8080/v1/auth/token")

def obtain_dynamic_jwt(client_id: str, client_secret: str) -> str:
    """Mengambil JWT runtime via OAuth2 client_credentials flow."""
    try:
        response = requests.post(
            AUTH_SERVICE_URL,
            json={"clientId": client_id, "clientSecret": client_secret},
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.RequestException as exc:
        sys.stderr.write(f"[FATAL] Auth failure: {exc}\n")
        sys.exit(1)

# Inisialisasi schema Schemathesis dari file lokal
schema = schemathesis.from_path(OPENAPI_SPEC_PATH, base_url=TARGET_BASE_URL)

# Generate Bearer token
ADMIN_TOKEN = obtain_dynamic_jwt("sec-scanner-admin", "SuperSecureCreds#2026")
REGULAR_USER_TOKEN = obtain_dynamic_jwt("sec-scanner-user", "UserPass#2026")

@schemathesis.hook
def before_call(context, case: Case):
    """Mutasi headers secara dinamis sebelum payload dikirimkan ke target."""
    # Menargetkan pengujian Broken Object Level Authorization (BOLA)
    # Jika path mengandung parameter tenant, uji dengan token non-admin
    if "/admin/" in case.path:
        case.headers["Authorization"] = f"Bearer {REGULAR_USER_TOKEN}"
    else:
        case.headers["Authorization"] = f"Bearer {ADMIN_TOKEN}"
    
    case.headers["X-Security-Scan"] = "SecOps-Automated-DAST-Engine"

# Custom security assertion: Cek status code leakage & SQLi patterns pada response error
def security_assertion(response, case: Case):
    # Dilarang mengembalikan HTTP 500 (Unhandled Exceptions menunjukkan celah fuzzing)
    assert response.status_code != 500, f"HTTP 500 Server Crash Detected at {case.path}"
    
    # Deteksi Database Error Signature Leaks
    db_signatures = [
        "pg_query()", "syntax error at or near", "ORA-00936",
        "DriverInfo", "com.mysql.cj.jdbc.exceptions"
    ]
    for sig in db_signatures:
        assert sig not in response.text, f"Database Information Disclosure [{sig}] at {case.path}"

def main():
    print(f"[*] Starting DAST Stateful Fuzzing against: {TARGET_BASE_URL}")
    runner = schema.runner(
        checks=[not_a_server_error, security_assertion],
        hypothesis_settings={"max_examples": 50, "deadline": None}
    )

    failures = 0
    for event in runner.execute():
        if event.status == schemathesis.runner.events.Status.failure:
            failures += 1
            print(f"[!] Security Flaw Detected: {event.check_name} on {event.data.path}")
            for error in event.errors:
                print(f"    - Payload info: {error.info}")

    if failures > 0:
        print(f"\n[FAILURE] DAST Fuzzing failed with {failures} discovered issues.")
        sys.exit(1)
    else:
        print("\n[SUCCESS] Dynamic schema fuzzing passed. Zero state anomalies detected.")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

#### 7.3 Advanced GitLab CI Pipeline Deployment Stage
File `.gitlab-ci.yml` yang menjalankan DAST secara asinkron dengan healthcheck:

```yaml
stages:
  - deploy_preview
  - security_dast
  - teardown

variables:
  PREVIEW_NAMESPACE: "dast-preview-${CI_COMMIT_SHORT_SHA}"

deploy_ephemeral_app:
  stage: deploy_preview
  image: alpine/k8s:1.29.2
  script:
    - kubectl create namespace ${PREVIEW_NAMESPACE}
    - helm upgrade --install target-app ./helm/app --namespace ${PREVIEW_NAMESPACE} --set image.tag=${CI_COMMIT_SHA}
    - kubectl rollout status deployment/target-app -n ${PREVIEW_NAMESPACE} --timeout=180s
    - echo "PREVIEW_URL=http://target-app.${PREVIEW_NAMESPACE}.svc.cluster.local:8080" >> deploy.env
  artifacts:
    reports:
      dotenv: deploy.env

zap_dast_scanning:
  stage: security_dast
  image: zaproxy/zap-stable:2.14.0
  needs: [deploy_ephemeral_app]
  variables:
    ZAP_PORT: 8090
  script:
    - mkdir -p /zap/wrk
    # Download file schema dari preview target
    - curl -f -s ${PREVIEW_URL}/v3/api-docs -o /zap/wrk/openapi.json
    # Jalankan ZAP headless Automation Framework
    - zap.sh -cmd -autorun /zap/configs/zap-pipeline.yaml -port ${ZAP_PORT}
    # Evaluasi Severity dengan Python Parser
    - python3 /zap/scripts/evaluate_sarif.py /zap/wrk/zap-results.sarif --fail-on=High,Critical
  artifacts:
    when: always
    paths:
      - /zap/wrk/zap-results.sarif
    reports:
      sast: /zap/wrk/zap-results.sarif

cleanup_preview:
  stage: teardown
  image: alpine/k8s:1.29.2
  when: always
  script:
    - kubectl delete namespace ${PREVIEW_NAMESPACE} --ignore-not-found=true
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Penetrasi API Gateway pada Core Banking Microservices
- **Konteks**: Lembaga perbankan dengan 120+ microservices yang mengadopsi GitOps. Mereka merilis build deployment 40 kali sehari. SAST bersih dari temuan (zero issues), tetapi audit pentest menemukan celah BOLA (*Broken Object Level Authorization*) pada endpoint `/v2/accounts/{accountId}/transfer-limits` yang memungkinkan user akun A mengubah limit transfer milik akun B.
- **Akar Masalah**: SAST tidak dapat mendeteksi dependensi runtime database access control yang berbasis claim token vs path parameter variable pada context thread Spring Security.
- **Implementasi Solusi DAST Terdistribusi**:
  1. **Deployment Architecture**: Dibuat pipeline DAST di mana setiap commit ke branch `main` men-trigger pembuatan *ephemeral environment* lengkap dengan mock Core Banking Interface (CBI).
  2. **Role Matrix Fuzzing**: Mengintegrasikan Schemathesis dengan matriks 3 level token (Role: Guest, Account Holder A, Account Holder B).
  3. **Otomasi Assertion**: Pipeline memverifikasi bahwa HTTP PUT request menggunakan Token A ke resource ID Akun B **harus selalu** mengembalikan HTTP `403 Forbidden`.
- **Hasil**:
  - DAST mendeteksi celah BOLA sebelum kode menyentuh Staging Environment.
  - Memangkas biaya manual penetration test dari $25,000/siklus menjadi pengujian terjadwal otomatis di CI/CD.
  - Zero false positive untuk logic vulnerability authorization layer.

---

### 9. Trade-offs

| Parameter | ZAP Full Scan (Spider + Active) | Spec-Driven Fuzzing (Schemathesis) | Headless Browser DAST |
| :--- | :--- | :--- | :--- |
| **Execution Time** | Sangat Lambat (30–90 menit) | Cepat (3–8 menit) | Sedang hingga Lambat (15–30 menit) |
| **State Complexity** | Rendah (Stateless crawler) | Sangat Tinggi (Property-based) | Tinggi (DOM-stateful) |
| **False Positive Rate** | Menengah ke Tinggi | Sangat Rendah | Menengah |
| **Target Coverage** | Menemukan unlinked pages | Hanya endpoint terdefinisi di OpenAPI | Resource Single Page Application (SPA) |
| **Resource Footprint** | CPU/Memory Tinggi (JVM) | CPU/Memory Rendah (Python/Rust) | Memory Sangat Tinggi (Chrome Engine) |
| **Impact on Target** | Berpotensi merusak data (Denial of Service/DB Bloat) | Terkendali melalui schema rules | Sedang (Tergantung actions) |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum:
1. **Memindai Database/Target Produksi secara Aktif**: Active scanner mengirim ribuan payload drop/insert/update yang merusak integritas database produksi atau memicu *alert fatigue* pada tim SOC.
   - *Solusi*: Batasi DAST Active scan **hanya** pada *ephemeral environment* atau staging database dengan data sintetik (*mock data*).
2. **Ketiadaan Session Synchronization**: Sesi login kedaluwarsa setelah 15 menit, mengakibatkan scanner melanjutkan scanning selama 45 menit berikutnya hanya terhadap halaman login HTTP `401 Unauthorized`.
   - *Solusi*: Gunakan auth token refresher sidecar script atau ZAP Zest authentication scripts yang memantau response pattern login verification.
3. **Triggering Anti-DDoS/Rate Limiting**: Target memblokir IP scanner dengan respons HTTP `429 Too Many Requests`, menyebabkan hasil pemindaian tidak lengkap.
   - *Solusi*: Konfigurasikan DAST scanner rate limit (misal: maximum 20 request/second) dan bypass WAF/Rate Limiter rule menggunakan dynamic secret custom header (`X-DAST-Bypass-Secret`).

#### Panduan Troubleshooting Ringkas:
- **Problem**: ZAP gagal mengurai response JSON API besar (Out of Memory).
  - *Fix*: Jalankan ZAP daemon dengan flag memory JVM: `zap.sh -Xmx4g -dir /zap/data`.
- **Problem**: Schemathesis meloloskan endpoint karena schema OpenAPI mengizinkan tipe data `anyOf` yang terlalu longgar.
  - *Fix*: Terapkan validasi `strict_types=True` dan linting schema menggunakan spectral (`spectral lint openapi.yaml`) sebelum DAST fuzzer dimulai.

---

### 11. Best Practices (Production Checklist)

#### Pre-Scanning:
- [ ] Schema OpenAPI/Swagger telah divalidasi dan tersinkronisasi dengan kode aktual.
- [ ] Database ephemeral diisolasi dan diisi data seed uji (*dummy accounts*).
- [ ] Dibuat 2 pasang kredensial login (User Alpha vs User Beta) untuk menguji segregasi hak akses (BOLA/BAC).
- [ ] Scanner dikonfigurasikan untuk mengabaikan endpoint berbahaya (misal: `/v1/system/purge-database` dimasukkan ke `excludeUrls`).

#### Scanning Execution:
- [ ] Scanner menyertakan custom identification header (`X-DevSecOps-DAST: True`).
- [ ] WAF preview environment mendeteksi header bypass untuk scanning tanpa memblokir payload.
- [ ] Rate limits dipasang rasional agar CPU cluster target tidak melebihi 85%.

#### Post-Scanning & Reporting:
- [ ] Filter laporan: Eliminasi temuan level "Info" dan "Low" dari threshold status CI pipeline.
- [ ] SARIF report dipublikasikan ke pipeline interface (GitHub Code Scanning atau GitLab Security Tab).
- [ ] Sinkronisasi otomatis temuan terverifikasi ke DefectDojo / Jira.
- [ ] Preview namespace dihancurkan (Kubernetes namespace destruction execution).

---

### 12. Hands-on Practice

Simpan seluruh file di direktori: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/target hands-on/m02/scanner hands-on/m02/reports
```

#### Langkah 1: Buat Dummy Vulnerable API Service
Simpan sebagai `hands-on/m02/target/app.py`:
```python
from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory mock database
USERS_DB = {
    "1001": {"name": "Alice", "role": "user", "ssn": "987-65-4321"},
    "1002": {"name": "Bob", "role": "user", "ssn": "123-45-6789"},
}

@app.route("/api/v1/auth/token", methods=["POST"])
def login():
    data = request.get_json() or {}
    if data.get("username") == "user_alice":
        return jsonify({"access_token": "token-alice-1001", "role": "user"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route("/api/v1/users/<user_id>", methods=["GET"])
def get_user_profile(user_id):
    # Kerentanan BOLA / Broken Authentication sengaja diekspos
    # Seharusnya memvalidasi user_id terhadap token pemanggil
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing token"}), 401
    
    user = USERS_DB.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    return jsonify(user)

@app.route("/api/v1/users/calculate-tax", methods=["POST"])
def calculate_tax():
    # Kerentanan Server Crash: Unhandled Exception jika field income bukan integer
    data = request.get_json()
    income = data["income"]
    tax = income * 0.15 # Throw TypeError jika income berupa string
    return jsonify({"tax": tax})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

#### Langkah 2: Buat Dokumentasi OpenAPI 3.0
Simpan sebagai `hands-on/m02/target/openapi.yaml`:
```yaml
openapi: 3.0.0
info:
  title: Vulnerable Target API
  version: 1.0.0
paths:
  /api/v1/auth/token:
    post:
      summary: Auth Token Login
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                username:
                  type: string
      responses:
        '200':
          description: OK
  /api/v1/users/{user_id}:
    get:
      summary: Get User Profile
      parameters:
        - name: user_id
          in: path
          required: true
          schema:
            type: string
      security:
        - BearerAuth: []
      responses:
        '200':
          description: User detail
  /api/v1/users/calculate-tax:
    post:
      summary: Calculate Income Tax
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - income
              properties:
                income:
                  type: integer
      responses:
        '200':
          description: Success
components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
```

#### Langkah 3: Buat Test Suite Automation Fuzzer
Simpan sebagai `hands-on/m02/scanner/test_fuzzer.py`:
```python
import os
import schemathesis
from schemathesis.checks import not_a_server_error

# Load schema lokal
schema = schemathesis.from_path(
    "hands-on/m02/target/openapi.yaml", 
    base_url="http://127.0.0.1:5000"
)

@schemathesis.check
def check_ssn_leakage(response, case):
    assert "987-65-4321" not in response.text, f"Critical PII (SSN) Leaked at {case.path}!"

@schemathesis.hook
def before_call(context, case):
    # Simulasi autentikasi
    case.headers["Authorization"] = "Bearer token-alice-1001"

def run_tests():
    print("[+] Launching Fuzzing Engine...")
    runner = schema.runner(
        checks=[not_a_server_error, check_ssn_leakage],
        hypothesis_settings={"max_examples": 20}
    )
    
    status = True
    for event in runner.execute():
        if event.status == schemathesis.runner.events.Status.failure:
            print(f"[-] Defect found on endpoint: {event.data.path}")
            for err in event.errors:
                print(f"    Reason: {err.info}")
            status = False
            
    return status

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
```

#### Langkah 4: Eksekusi dan Verifikasi
Jalankan langkah-langkah berikut via terminal:

```bash
# Terminal 1: Install requirements & Jalankan API Target
pip install flask schemathesis pyyaml
python3 hands-on/m02/target/app.py

# Terminal 2: Eksekusi Fuzzer Scanner
python3 hands-on/m02/scanner/test_fuzzer.py
```
*Hasil yang diharapkan*: Engine Schemathesis mengirimkan tipe string pada property `income` di `/calculate-tax`, memicu unhandled exception internal (HTTP 500) dan pipeline script akan mengembalikan exit status `1` (Fuzzer mendeteksi defect logic).

---

### 13. Exercise

#### Level Easy
Konfigurasikan script Python sederhana menggunakan library `requests` untuk melakukan passive scanning terhadap security headers (X-Frame-Options, Content-Security-Policy, Strict-Transport-Security, X-Content-Type-Options) dari URL lokal yang diberikan. Laporkan header apa saja yang hilang.

#### Level Medium
Buat automation script Bash yang mengeksekusi container OWASP ZAP via Docker (`zaproxy/zap-stable`) dalam mode `zap-baseline.py` terhadap target web internal. Ambil JSON output dari volume lokal, filter hanya temuan dengan `confidence >= Medium` dan `riskcode >= 2` (Medium/High), lalu cetak hasilnya dalam format markdown table ke console.

#### Level Hard
Rancang file konfigurasi ZAP Automation Framework (`zap.yaml`) yang:
1. Melakukan import OpenAPI specification dari endpoint `/v3/api-docs`.
2. Melakukan pre-authentication script (menggunakan JavaScript engine ZAP Zest atau custom headers) untuk injeksi token session.
3. Menjalankan active scanner dengan custom policy yang menonaktifkan checks SQL Injection lambat (Time-based blind SQLi), namun memprioritaskan Cross-Site Scripting (XSS), Parameter Tampering, dan Path Traversal.
4. Menghasilkan file SARIF (`zap-out.sarif`).

---

### 14. Challenge
**Skenario**: Anda adalah Lead DevSecOps Architect di Unicorn FinTech. Sebuah microservice pembayaran berbasis GraphQL (`/graphql`) akan dirilis ke cluster Kubernetes. Dokumentasi schema GraphQL tidak dibuka untuk publik (Introspection sengaja di-disable pada production, namun tersedia di staging). 

Microservice ini menggunakan mekanisme otentikasi asymmetric mTLS untuk machine-to-machine, ditambah enkripsi payload di level aplikasi (JWE - JSON Web Encryption) sebelum request dikirim melalui network wire.

**Tantangan**:
Rancang arsitektur dynamic security testing (DAST) terintegrasi pada CI/CD pipeline yang mampu:
1. Memotong (*intercept*) dan melakukan dynamic contract testing pada endpoint GraphQL terenkripsi tersebut.
2. Menyediakan ephemeral certificate authority (CA) untuk menangani handshake mutual TLS secara otomatis di pipeline runner tanpa membocorkan private key corporate.
3. Melakukan fuzzer mutation payload terhadap schema GraphQL tanpa memicu invalid decryption exception pada layer reverse-proxy/API gateway.
4. Buat arsitektur pipeline deklaratif dan cetak biru topologi ASCII untuk memecahkan skenario ini secara utuh.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic:
1. Apa perbedaan mendasar antara Dynamic Application Security Testing (DAST) dan Static Application Security Testing (SAST)?
2. Mengapa DAST rentan terhadap kendala scanning ketika aplikasi menggunakan SPA (Single Page Application) berbasis JavaScript modern?
3. Apa fungsi file OpenAPI / Swagger dalam pengujian keamanan DAST untuk API?
4. Mengapa HTTP Status Code 500 (Internal Server Error) dianggap sebagai temuan defect keamanan saat proses API fuzzing berlangsung?
5. Apa resiko utama menjalankan active DAST scan secara langsung pada lingkungan Production?

#### 5 Pertanyaan Intermediate:
6. Bagaimana cara scanner DAST mempertahankan status autentikasi ketika target mengimplementasikan *short-lived* JWT tokens (masa berlaku < 10 menit)?
7. Mengapa pengujian DAST API berbasis brute-force crawler tradisional (web crawling spider) kurang efektif jika dibandingkan dengan *property-based schema testing*?
8. Bagaimana format standard SARIF menyederhanakan agregasi temuan dari tools DAST, SAST, dan SCA ke dalam platform sentral DevSecOps?
9. Apa fungsi header `X-Security-Scan` atau header bypass serupa dalam integrasi DAST dengan arsitektur microservices yang diproteksi oleh Web Application Firewall (WAF)?
10. Bagaimana mekanisme penentuan status kelulusan (Quality Gate) berbasis skor CVSS v3 pada pipeline DAST enterprise?

#### 3 Skenario Kasus Produksi:
11. **Skenario 1**: ZAP Active Scan Anda menyebabkan cluster test database kehabisan koneksi (*Connection Pool Exhaustion*) dalam waktu 2 menit sejak pipeline berjalan, sehingga ratusan test request lainnya mengembalikan `HTTP 503 Service Unavailable`. Bagaimana Anda merekonfigurasi ZAP engine dan target setup untuk mengatasi hal ini?
12. **Skenario 2**: Pipeline CI/CD Anda memindai API menggunakan contract OpenAPI. Developer mengubah skema tipe data field `user_age` dari integer ke array of strings di repositori kode tanpa memperbarui `openapi.yaml`. Apa dampak langsungnya terhadap scanner DAST berbasis kontrak, dan tindakan preventif apa yang harus diotomatisasi pada pipeline?
13. **Skenario 3**: Tim QA dan Tim SecOps mengeluhkan bahwa pipeline DAST memakan waktu 85 menit, memperlambat proses deployment sprint release secara signifikan. Langkah optimasi arsitektural apa yang dapat Anda terapkan untuk memangkas waktu eksekusi scan menjadi di bawah 15 menit tanpa mengurangi coverage endpoint kritikal?

---

### 16. Summary
- DAST memvalidasi keamanan aplikasi dari perspektif *adversary outside-in*, memverifikasi celah pada *running state*, konfigurasi runtime, dan parsing network protocol.
- Integrasi DAST modern pada lingkungan API menuntut otomasi yang berbasis **kontrak (OpenAPI/Swagger)**, bukan web spidering tradisional.
- Tantangan terbesar implementasi DAST enterprise adalah pengelolaan sesi autentikasi, isolasi data, dan durasi eksekusi pemindaian.
- Solusi standar industri melibatkan penggunaan *ephemeral Kubernetes preview environments*, *dynamic JWT sidecar provisioning*, serta integrasi *property-based fuzzing tools* (seperti Schemathesis dan OWASP ZAP Automation Framework).
- Pipeline DAST wajib dilengkapi *quality gate* berbasis SARIF/DefectDojo untuk mencegah vulnerability berisiko tinggi (High/Critical) lolos ke lingkungan produksi secara otomatis.