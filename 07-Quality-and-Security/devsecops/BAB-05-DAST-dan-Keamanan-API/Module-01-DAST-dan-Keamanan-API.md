# Bab 05 Module 01: Dynamic Application Security Testing (DAST) & Keamanan API

---

### 1. Identitas Modul
* **Track:** DevSecOps Engineering
* **Kategori:** 07-Quality-and-Security
* **Bab:** 05 – Dynamic Application Security Testing (DAST) & Keamanan API
* **Tingkat Kesulitan:** Advanced / Enterprise Professional
* **Prasyarat:**
  * Pemahaman arsitektur HTTP/HTTPS, TLS, RESTful, GraphQL, dan protokol gRPC (HTTP/2, Protobuf).
  * Penguasaan pipeline CI/CD (GitHub Actions / GitLab CI) dan containerization (Docker).
  * Pengetahuan dasar Static Application Security Testing (SAST) dan Software Bill of Materials (SBOM).
  * Pemahaman OWASP Top 10 Web & OWASP API Security Top 10.
* **Estimasi Waktu:** 12 Jam Pembelajaran (6 Jam Teori & Arsitektur, 6 Jam Hands-on Lab & Implementasi Pipeline).

---

### 2. Learning Objectives
* **LO-01:** Menganalisis perbedaan arsitektur, kapabilitas, serta limitasi antara SAST, DAST, dan Interactive Application Security Testing (IAST).
* **LO-02:** Mengotomatisasikan eksekusi DAST (OWASP ZAP Baseline, Full Scan, dan API Scan) di dalam pipeline CI/CD dengan thresholding dan vulnerability gating berbasis CVSS/CWE.
* **LO-03:** Merancang strategi pengujian keamanan API spesifik untuk arsitektur REST, GraphQL (Introspection, Batching, Depth Limit), dan gRPC (Reflection, TLS enforcement).
* **LO-04:** Mengidentifikasi dan memitigasi 10 kerentanan kritis berdasarkan OWASP API Security Top 10 (2023).
* **LO-05:** Mengoperasikan teknik Web Application Fuzzing terarah menggunakan instrumen seperti `ffuf` untuk mendeteksi hidden endpoints, parameter polusi, dan unhandled exception states.
* **LO-06:** Mengintegrasikan IAST agent ke dalam runtime application container untuk observabilitas aliran data (data flow tracking) dan verifikasi eksploitasi instan tanpa overhead network scanning konvensional.
* **LO-07:** Membangun strategi mitigasi teknis berbasis code-level (input validation, rate limiting, context-aware authorization) untuk mengatasi kelemahan BOLA/BFLA.
* **LO-08:** Menyusun laporan temuan DAST terstruktur dan mengintegrasikan hasil ke dalam vulnerability management dashboard (DefectDojo/Jira).

---

### 3. Concept Map & Architecture Diagram

```
+---------------------------------------------------------------------------------------------------+
|                                 CI/CD PIPELINE INTEGRATION RUNTIME                                |
+---------------------------------------------------------------------------------------------------+
                                                  |
           +--------------------------------------+--------------------------------------+
           |                                                                             |
           v                                                                             v
+-----------------------+                                                     +---------------------+
|   Ephemerality Stage  |                                                     | Ingress / API GW    |
| (Docker/K8s Test Pod) |                                                     | (Kong/Envoy/Tyk)    |
|                       |                                                     +----------+----------+
|  +-----------------+  |                                                                |
|  | Target App Pod  |  |                                                                |
|  | +-------------+ |  |                                                                |
|  | | IAST Agent  | |  |                                                                |
|  | | (Runtime    | |  |                                                                |
|  | | Sensor/Sink)| |  |                                                                v
|  | +------+------+ |  |                                                     +---------------------+
|  |        |        |  |                                                     |   Microservices     |
|  |        v        |  |                                                     |                     |
|  | App Core Logic  |  |                                                     | [REST / GraphQL /   |
|  +--------^--------+  |                                                     |  gRPC Endpoints]    |
+-----------|-----------+                                                     +----------^----------+
            |                                                                            |
            | (Internal Hooks)                                                           | (External Ingress)
            |                                                                            |
+-----------v-----------+         HTTP/1.1 & HTTP/2 Requests (Tainted)        +----------v----------+
| Vulnerability Telemetry| <===================================================|  DAST SCANNER ENGINE |
| (IAST Correlator)     |                                                     |  (OWASP ZAP / ffuf) |
+-----------+-----------+                                                     +----------+----------+
            |                                                                            |
            |                                                                            | (OpenAPI/GraphQL Spec)
            |                                                                 +----------v----------+
            +------------------------------------+----------------------------| Schema Parser & Auth|
                                                 |                            | (Bearer Token Pool) |
                                                 v                            +---------------------+
                                    +--------------------------+
                                    | Pipeline Gate Decision   |
                                    | High/Critical CVSS > 7.0 |
                                    | Exit Code: 0 (Pass) / 1  |
                                    +--------------------------+
```

---

### 4. Mengapa Ini Penting
Pengujian statis (SAST) sering kali tidak mampu mendeteksi cacat konfigurasi runtime, otentikasi token yang rusak, atau logika bisnis yang hanya termanifestasi saat aplikasi berjalan di lingkungan target. DAST dan API Security Testing memegang peranan krusial karena beberapa faktor:

1. **Blind Spot SAST:** SAST menganalisis kode mati. SAST tidak mengeksekusi logika jaringan, tidak memahami *misconfiguration* pada reverse proxy/web server, dan tidak mampu memvalidasi apakah kerentanan teoritis benar-benar terekspos ke permukaan jaringan.
2. **Pergeseran Monolitik ke API-Driven Architecture:** Aplikasi modern memecah logika presentasi dari data layer. Penggunaan REST, GraphQL, dan gRPC mentransformasi permukaan serangan dari skrip sisi server berbasis HTML menjadi ratusan endpoint API yang sering kali terpapar langsung tanpa validasi otorisasi terpusat.
3. **Konsekuensi Finansial dan Operasional:** Cacat logika otorisasi seperti Broken Object Level Authorization (BOLA) memungkinkan peretas mengakses data pelanggan lain secara masif. Ini menyebabkan kebocoran data terstruktur berskala besar, denda regulasi (GDPR, PDP), serta hilangnya reputasi bisnis secara permanen.
4. **Verifikasi Fungsional:** DAST bertindak layaknya adversary eksternal yang tidak memiliki hak istimewa terhadap kode sumber (*black-box/gray-box*), memvalidasi efektivitas *defense-in-depth* seperti Web Application Firewall (WAF), HTTP security headers, dan sistem token exchange.

---

### 5. Apa Itu Konsep
* **Dynamic Application Security Testing (DAST):** Metodologi pengujian keamanan aplikasi berbasis kotak hitam (*black-box*) atau abu-abu (*gray-box*) di mana aplikasi diuji dalam keadaan berjalan (*running state*) melalui antarmuka jaringannya. DAST mengirimkan ribuan muatan anomali (fuzzing/attack vectors) ke endpoint dan menganalisis respon HTTP/TCP untuk menemukan kerentanan.
* **IAST (Interactive Application Security Testing):** Hibrida antara SAST dan DAST. Agen IAST diinjeksikan ke dalam runtime aplikasi (misalnya JVM, Node.js runtime, atau Python runtime). Agen ini memantau eksekusi kode internal, penanganan memori, serta query database (*sinks*) saat DAST atau functional automation suite (Selenium/Playwright) berinteraksi dengan API (*sources*).
* **API Security Testing:** Disiplin pengujian yang berfokus secara ketat pada kontrak API, status otentikasi/otorisasi, manipulasi skema (*state validation*), serta batasan beban (*rate limiting/DoS*) pada protokol pertukaran data terstruktur (JSON, Protobuf) tanpa ketergantungan pada Graphical User Interface (GUI).
* **Fuzzing (Web/API):** Pengujian keandalan dan keamanan dengan cara menyuntikkan data semi-acak, tidak terduga, atau mutasi payload secara sistematis ke dalam parameter, header, atau URI untuk mendeteksi *unhandled exceptions*, kebocoran data, atau *crash* pada server.

---

### 6. Bagaimana Cara Kerjanya
Alur mekanika internal DAST modern terbagi menjadi empat fase utama:

1. **Discovery & Crawling (Spidering):**
   * **Traditional Spider:** Menganalisis dokumen HTML, mengekstrak tag `<a href>`, `<form action>`, serta parsing skrip JavaScript untuk mengidentifikasi URL target.
   * **API-Driven Parsing:** DAST modern tidak menggunakan perayap web biasa untuk API, melainkan mengonsumsi skema formal: file OpenAPI/Swagger (REST), skema SDL/Introspection query (GraphQL), atau Proto files/Reflection service (gRPC) untuk membangun pemetaan endpoint secara akurat.
2. **Session & Authentication Handling:**
   * DAST mengonfigurasi siklus hidup sesi melalui header injection (OAuth2 Bearer tokens, API Keys, mTLS certificates). Scanner harus mampu melakukan re-autentikasi otomatis jika token kedaluwarsa selama proses pemindaian berlangsung.
3. **Attack Generation & Fuzzing (Active Scan):**
   * Scanner mengisolasi parameter (query string, body JSON, header HTTP) dan menyuntikkan payload spesifik CWE (SQLi, XSS, Path Traversal, SSRF).
   * Engine mengevaluasi status kode HTTP, respon latensi waktu (misal: *time-based injection*), panjang byte, dan struktur error respons.
4. **Analysis & False Positive Reduction:**
   * Scanner membandingkan respon baseline normal dengan respon hasil uji.
   * Pada integrasi IAST, sinyal dari runtime agent memverifikasi apakah payload uji mencapai baris kode eksekusi (*sink*) yang rentan, mengeliminasi temuan palsu (*false positives*).

---

### 7. Perbandingan Paradigma / Taksonomi Matriks

| Atribut / Metrik | SAST | DAST | IAST | Web/API Fuzzing |
| :--- | :--- | :--- | :--- | :--- |
| **Fase SDLC** | Build / Code | Test / Staging / Deploy | Integration Test / QA | Test / Staging |
| **Perspektif** | White-box (Source Code) | Black-box / Gray-box | Gray-box (Sensor Inside) | Black-box (Network Edge) |
| **Kebutuhan Runtime**| Tidak Aktif | Wajib Berjalan | Wajib Berjalan | Wajib Berjalan |
| **False Positive** | Tinggi (Banyak Noise) | Sedang | Sangat Rendah | Bervariasi (Butuh Triase) |
| **Cakupan Kerentanan**| Cacat sintaksis, hardcoded secret, dependensi | Misconfiguration, SSL/TLS, Session Flaws, BOLA | Sink-to-Source Tracking, Cacat Runtime | Crash, Logic Flaw, Buffer Overflow, DoS |
| **Deteksi Logic Flaws**| Sangat Rendah | Rendah - Sedang | Sedang | Sedang |
| **Dampak Performa**| Menambah waktu kompilasi | Membebani jaringan & log target | Menambah latency eksekusi target (5-15%) | Sangat tinggi pada throughput server |

---

### 8. Analisis Mendalam Attack Surface & Vector Matrix

| Kode OWASP API | Nama Kerentanan | Mekanisme Vektor Serangan | Karakteristik Signature Respon | Dampak Sistemik |
| :--- | :--- | :--- | :--- | :--- |
| **API1:2023** | Broken Object Level Authorization (BOLA) | Memanipulasi parameter ID (`/users/{id}`) pada request dengan token milik identitas lain. | HTTP `200 OK` dengan data milik subjek lain alih-alih `403 Forbidden`. | Akses dan eksfiltrasi data horizontal berskala masif. |
| **API2:2023** | Broken Authentication | Serangan brute-force pada endpoint token, kelemahan implementasi JWT (alg: none, signature bypass). | HTTP `200 OK` tanpa verifikasi cryptographic signature yang valid. | Pengambilalihan akun secara menyeluruh (*full identity impersonation*). |
| **API3:2023** | Broken Object Property Level Authorization | Mass Assignment: Menyuntikkan property privat pada JSON payload (misal: `{"is_admin": true}`). | Properti terupdate di DB, respon memantulkan properti yang dilarang. | Eskalasi hak akses privilege (*privilege escalation*). |
| **API4:2023** | Unrestricted Resource Consumption | Mengirim request berulang tanpa limit, GraphQL nested query dalam skala tak terbatas, payload Protobuf raksasa. | Latensi respons meningkat tajam (>5000ms), disusul HTTP `504 Gateway Timeout` atau `502`. | Server kehabisan resource memori/CPU (*Denial of Service*). |
| **API5:2023** | Broken Function Level Authorization (BFLA) | Mengganti metode HTTP (GET ke DELETE) atau memanggil endpoint administratif (`/api/admin/system`). | HTTP `200 OK` atau `204 No Content` dieksekusi oleh akun dengan role non-admin. | Eksekusi fungsi administratif oleh user regular. |
| **API6:2023** | Unrestricted Access to Sensitive Business Flows | Eksploitasi otomatisasi (bot) pada fungsionalitas pembelian, reservasi tiket, atau pengiriman SMS OTP massal. | Lonjakan request HTTP `200 OK` secara serentak dari subnet yang sama. | Penipuan bisnis, kerugian finansial kuota SMS gateway, penimbunan inventaris. |
| **API7:2023** | Server-Side Request Forgery (SSRF) | Menyisipkan URL internal (`http://169.254.169.254` atau `http://localhost:8080`) pada parameter webhook/callback API. | Respon mengandung data metadata cloud atau HTTP `200` dari subnet lokal internal. | Kompromi metadata AWS/GCP, peretasan jaringan privat internal. |
| **API8:2023** | Lack of Protection from Automated Threats | Kurangnya deteksi captcha, antrean bot, device fingerprinting pada request API. | Pola scraping massal tanpa throttling yang berhasil mengambil seluruh dataset. | Pelanggaran privasi, pencurian kekayaan intelektual (IP scraping). |
| **API9:2023** | Improper Inventory Management | Penyerangan terhadap endpoint versi lama (`/api/v1/users`) yang sudah tidak dipelihara dan minim proteksi. | Endpoint versi lawas membalas dengan struktur skema usang tanpa auth middleware baru. | Bypass kontrol keamanan terkini melalui interface lama (*shadow API*). |
| **API10:2023** | Unsafe Consumption of APIs | Mengabaikan validasi input dari data yang diterima dari API pihak ketiga (upstream service). | Injeksi payload terselubung via respon pihak ketiga ke core engine aplikasi. | SQLi, remote code execution (RCE) via inter-service chain poisoning. |

---

### 9. Code Example Sederhana: Basic OWASP ZAP Automation Script

Skrip Python berikut mengotomatisasi pemindaian pasif dan aktif pada satu endpoint REST API menggunakan OWASP ZAP API Client.

```python
#!/usr/bin/env python3
"""
Baseline DAST runner menggunakan ZAP API Client v2.4
Mekanisme: Akses target -> Spidering -> Validasi Alert Pasif
"""

import time
import sys
from zapv2 import ZAPv2

# Konfigurasi Akses ZAP Daemon
ZAP_ADDRESS = 'http://127.0.0.1'
ZAP_PORT = '8080'
API_KEY = 'change-me-api-key-zap' # Kunci otentikasi ZAP Daemon
TARGET_URL = 'http://target-api.internal:8000/api/v1/health'

zap = ZAPv2(proxies={'http': f'{ZAP_ADDRESS}:{ZAP_PORT}', 
                      'https': f'{ZAP_ADDRESS}:{ZAP_PORT}'}, 
            apikey=API_KEY)

print(f"[*] Menghubungkan ke ZAP Engine: {ZAP_ADDRESS}:{ZAP_PORT}")

# Mengakses target untuk menginisialisasi context di ZAP
zap.core.access_url(url=TARGET_URL)
time.sleep(2)

# Menjalankan Spidering
print(f"[*] Memulai Spidering URL: {TARGET_URL}")
scan_id = zap.spider.scan(url=TARGET_URL)

while int(zap.spider.status(scan_id)) < 100:
    print(f"[-] Spider Progress: {zap.spider.status(scan_id)}%")
    time.sleep(1)

print("[+] Spidering Selesai.")

# Menunggu pasif scanner menyelesaikan analisis antrean respon
while int(zap.pscan.records_to_scan) > 0:
    print(f"[-] Menunggu Passive Scan: {zap.pscan.records_to_scan} record tersisa...")
    time.sleep(1)

print("[+] Passive Scan Selesai. Mengambil alerts...")

# Evaluasi Alert Keamanan
alerts = zap.core.alerts(baseurl=TARGET_URL)
critical_alerts = [a for a in alerts if a['risk'] in ['High', 'Medium']]

if critical_alerts:
    print(f"[!] Gate Gagal: Ditemukan {len(critical_alerts)} kerentanan High/Medium!")
    for alert in critical_alerts:
        print(f"    - [{alert['risk']}] {alert['alert']} pada URL: {alert['url']}")
    sys.exit(1)
else:
    print("[+] Gate Berhasil: Tidak ditemukan kerentanan berisiko High atau Medium.")
    sys.exit(0)
```

---

### 10. Code Example Lanjutan: Production CI/CD DAST Stage dengan OpenAPI Import, Auth Handling, dan Vulnerability Gating

Pipeline GitHub Actions berikut menjalankan DAST terisolasi pada ephemeral container:
1. Menjalankan mock/test target API.
2. Mengonfigurasi ZAP via Docker, mengimpor OpenAPI 3.0 specification.
3. Menginjeksi OAuth2 Bearer token otomatis.
4. Melakukan active scan terarah dan menerjemahkan output SARIF/JSON untuk decision gating.

```yaml
name: DevSecOps API DAST Pipeline

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  dast-api-scan:
    name: Execute Dynamic API Security Gate
    runs-on: ubuntu-latest
    
    services:
      # Jalankan target API internal sebagai ephemeral test runner
      api-target:
        image: ghcr.io/my-org/enterprise-api:staging-test
        env:
          NODE_ENV: test
          DB_HOST: memory
        ports:
          - 8080:8080

    steps:
      - name: Checkout Code Repository
        uses: actions/checkout@v4

      - name: Generate Ephemeral Test JWT Token
        id: generate-auth
        run: |
          # Ekstraksi atau generate token test untuk scanner context
          TEST_TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/token \
            -H "Content-Type: application/json" \
            -d '{"client_id": "${{ secrets.TEST_CLIENT_ID }}", "client_secret": "${{ secrets.TEST_CLIENT_SECRET }}"}' \
            | jq -r .access_token)
          echo "::add-mask::$TEST_TOKEN"
          echo "BEARER_TOKEN=$TEST_TOKEN" >> $GITHUB_ENV

      - name: Prepare Scanner Directories and Permissions
        run: |
          mkdir -p zap_reports
          chmod 777 zap_reports

      - name: Run OWASP ZAP API Scan via Docker
        run: |
          # Mount OpenAPI Spec dan jalankan zap-api-scan.py
          docker run --net="host" -v $(pwd)/zap_reports:/zap/wrk/:rw \
            zaproxy/zap-stable:2.14.0 zap-api-scan.py \
            -t http://localhost:8080/openapi/v1/spec.json \
            -f openapi \
            -d \
            -r report.html \
            -J report.json \
            -w report.md \
            --hook=/zap/wrk/zap_hooks.py \
            -z "-config replacer.full_list(0).description=auth \
                -config replacer.full_list(0).enabled=true \
                -config replacer.full_list(0).matchtype=REQ_HEADER \
                -config replacer.full_list(0).matchstr=Authorization \
                -config replacer.full_list(0).regex=false \
                -config replacer.full_list(0).replacement='Bearer ${{ env.BEARER_TOKEN }}'"
        continue-on-error: true

      - name: Evaluate Security Gate Thresholds
        run: |
          python3 - << 'EOF'
          import json
          import sys

          try:
              with open('zap_reports/report.json', 'r') as f:
                  data = json.load(f)
          except Exception as e:
              print(f"CRITICAL: Laporan ZAP tidak ditemukan atau corrupt: {e}")
              sys.exit(1)

          site_data = data.get('site', [])
          high_count = 0
          medium_count = 0
          alerts_summary = []

          for site in site_data:
              for alert in site.get('alerts', []):
                  riskcode = int(alert.get('riskcode', 0))
                  # 3 = High, 2 = Medium
                  if riskcode == 3:
                      high_count += 1
                      alerts_summary.append(f"[HIGH] {alert.get('name')} -> {alert.get('instances', 0)} instances")
                  elif riskcode == 2:
                      medium_count += 1
                      alerts_summary.append(f"[MEDIUM] {alert.get('name')} -> {alert.get('instances', 0)} instances")

          print("--- HASIL PENGUJIAN DAST GATE ---")
          for entry in alerts_summary:
              print(entry)
          print(f"Total High: {high_count}, Total Medium: {medium_count}")

          # Security Gate Policy Enforcement
          if high_count > 0:
              print("Pipeline Dibatalkan: Ditemukan kerentanan tingkat HIGH pada API endpoint.")
              sys.exit(1)
          if medium_count > 3:
              print("Pipeline Dibatalkan: Melebihi batas toleransi MEDIUM (> 3).")
              sys.exit(1)

          print("Security Gate Terpenuhi. Melanjutkan proses deployment.")
          sys.exit(0)
          EOF

      - name: Archive Security Artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: dast-api-reports
          path: zap_reports/
```

---

### 11. Diagram Alur Serangan & Mitigasi: Broken Object Level Authorization (BOLA)

```
[ATTACK EXECUTION FLOW - BOLA]
Attacker (User-A: ID 901)          API Gateway                 User Service               Database
        |                              |                             |                       |
        | [1] GET /users/902/profile   |                             |                       |
        |     Auth: Bearer Token-User-A|                             |                       |
        +----------------------------->|                             |                       |
        |                              | [2] Validasi Token JWT      |                       |
        |                              |     (Signature: VALID)      |                       |
        |                              |     (Claims: sub=901)       |                       |
        |                              +---------------------------->|                       |
        |                              |                             | [3] Query langsung:   |
        |                              |                             |     SELECT * FROM usr |
        |                              |                             |     WHERE id = 902    |
        |                              |                             +---------------------->|
        |                              |                             |                       |
        |                              |                             | [4] Return Record 902 |
        |                              |                             |<----------------------+
        |                              | [5] Response: Data User-902 |                       |
        | [6] Respon 200 OK (LEAKED)   |<----------------------------+                       |
        |<-----------------------------+                                                     |

===================================================================================================

[DEFENSE & MITIGATION FLOW - CONTEXT-AWARE ABAC ENFORCEMENT]
Attacker (User-A: ID 901)          API Gateway                 User Service               Database
        |                              |                             |                       |
        | [1] GET /users/902/profile   |                             |                       |
        |     Auth: Bearer Token-User-A|                             |                       |
        +----------------------------->|                             |                       |
        |                              | [2] Validasi Token & Injeksi|                       |
        |                              |     Header: X-Caller-Id=901 |                       |
        |                              +---------------------------->|                       |
        |                              |                             | [3] Otorisasi Konteks:|
        |                              |                             |     Caller == Target? |
        |                              |                             |     901 != 902 (FALSE)|
        |                              |                             |                       |
        |                              |                             | [4] Access Denied     |
        |                              |                             |     Audit Log Alert   |
        |                              | [5] Error 403 Forbidden     |                       |
        | [6] Respon 403 FORBIDDEN     |<----------------------------+                       |
        |<-----------------------------+                                                     |
```

---

### 12. Trade-offs & Security vs Usability / Performance

1. **Waktu Pipeline vs Kedalaman Pemindaian (Scan Duration vs Scan Depth):**
   * *Baseline Scan:* Mengeksekusi passive scanning dan pemeriksaan konfigurasi dasar dalam rentang 2-5 menit. Tidak menguji injeksi mendalam, sehingga menyisakan celah BOLA atau SQLi kompleks.
   * *Active Scan:* Melakukan ribuan mutasi muatan yang memakan waktu 30-180 menit. Tidak realistis diintegrasikan langsung pada pipeline *PR Validation*, melainkan harus dipindahkan ke *Nightly Scheduled Runs* atau trigger rilis staging.
2. **State Pollution vs State Isolation (Database Mutation):**
   * DAST memicu HTTP `POST`, `PUT`, dan `DELETE`. Jika scanning diarahkan ke staging environment yang persisten, pengujian ini dapat mencemari integritas data fungsional, memicu pengiriman email notifikasi massal ke end-user riil, atau menghabiskan kuota transaksi.
   * *Mitigasi:* Jalankan target API pada ephemeral Docker environment yang diisolasi dengan mock upstream services dan database *in-memory* yang dimusnahkan pasca pemindaian selesai.
3. **WAF Interception vs Scanner Accuracy:**
   * Menjalankan DAST di depan Web Application Firewall (WAF) aktif hanya menguji keandalan rule WAF, bukan postur keamanan aktual dari kode aplikasi itu sendiri (*false sense of security*).
   * DAST internal harus dioperasikan di balik layer WAF (*internal perimeter*) untuk mengevaluasi kerentanan riil aplikasi (*defense-in-depth*).

---

### 13. Edge Cases & Complex Failure Modes
* **Token Expiration / Invalidation:** Active scan berjalan selama 45 menit, sementara lifespan JWT target diset ke 15 menit. Pada menit ke-16, seluruh request DAST berikutnya menerima respon `401 Unauthorized`. Scanner menafsirkan aplikasi kebal serangan, menghasilkan **False Negatives total**. Solusinya adalah menggunakan ZAP authentication scripts yang memantau status respon dan mengeksekusi refresh token secara deterministik.
* **GraphQL Circular Nesting & Denial of Service:** Endpoint GraphQL tanpa pembatasan kedalaman (depth limiting) dapat membuat engine database target mengalami *high CPU exhaustion* ketika DAST scanner mengirimkan rekursif query (misal: `author { books { author { books { ... } } } }`). Scanner dapat merusak kestabilan target staging dan mematikan pipeline testing lainnya.
* **gRPC Serialization Errors:** Scanner HTTP konvensional tidak dapat membaca skema Protobuf biner secara default. Paket dianggap malformed oleh gRPC server (`Status Code: 3 - INVALID_ARGUMENT`), menyebabkan scanner tidak mampu memetakan *business logic sinks* tanpa pemanfaatan Reflection Service atau file `.proto` ingestion.
* **Rate Limiting Engine Blocking Scanner:** Modul anti-bruteforce internal memblokir IP runner DAST setelah 100 request pertama. 99% alur scanning berikutnya gagal dan memicu status `429 Too Many Requests`, yang terlewat dari evaluasi kerentanan.

---

### 14. Anti-Patterns & Common Vulnerabilities

#### A. Dependensi Total pada UI Crawling untuk API Testing
* *Anti-Pattern:* Menggunakan ZAP Spider standar yang mengklik tombol browser HTML untuk menemukan endpoint API.
* *Dampak:* 80% endpoint privat (khususnya yang hanya dipanggil secara dinamis via async JavaScript calls atau service-to-service) tidak pernah teridentifikasi atau diuji.
* *Solusi:* Injeksi spesifikasi kontrak mesin langsung (OpenAPI, Postman Collections, GraphQL AST, Protobuf descriptors).

#### B. Mass Assignment Vulnerability
* *Anti-Pattern:* Menerima entitas DTO (Data Transfer Object) langsung ke dalam representasi Database Model pada ORM.

```python
# KODE RENTAN (Anti-Pattern)
@app.route('/api/v1/user/update', methods=['PUT'])
@jwt_required()
def update_profile():
    user = User.query.get(get_jwt_identity())
    # Bahaya: Jika client mengirimkan {"role": "superadmin"}, 
    # field atribut privilege akan langsung ter-overwrite di database.
    data = request.get_json()
    for key, value in data.items():
        setattr(user, key, value)
    db.session.commit()
    return jsonify({"status": "updated"})
```

#### C. Inadequate GraphQL Query Complexity Controls
* *Anti-Pattern:* Membiarkan endpoint `/graphql` memproses batching query dan nested traversal tanpa batasan biaya operasional.

```graphql
# Serangan Query Batching Amplification DoS
query {
  q1: user(id: 1) { sensitiveData }
  q2: user(id: 2) { sensitiveData }
  q3: user(id: 3) { sensitiveData }
  # ... diulang 500x dalam satu HTTP Request payload
}
```

---

### 15. Best Practices & Enterprise Remediation Guide

1. **Context-Aware Object Authorization Engine:** Terapkan pemeriksaan kepemilikan eksplisit pada domain entity layer, bukan hanya di level edge gateway.

```python
# KODE AMAN (Remediasi Terverifikasi)
@app.route('/api/v1/user/profile', methods=['PUT'])
@jwt_required()
def safe_update_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    # Whitelisting ketat menggunakan Schema Validation (Marshmallow / Pydantic)
    update_data = request.get_json()
    allowed_fields = {'bio', 'phone_number', 'avatar_url'}
    
    for key, value in update_data.items():
        if key in allowed_fields:
            setattr(user, key, value)
        else:
            # Drop atau log deteksi parameter polusi
            pass
            
    db.session.commit()
    return jsonify({"status": "success", "message": "Profile updated."}), 200
```

2. **GraphQL Query Hardening:**
   * Nonaktifkan Introspection pada production environment.
   * Terapkan `graphql-depth-limit` maksimal 4 atau 5 level.
   * Gunakan `graphql-query-complexity` analyzer untuk menolak query dengan cost kalkulasi tinggi sebelum eksekusi database.
3. **gRPC Protocol Hardening:**
   * Wajibkan otentikasi Mutual TLS (mTLS) antar microservice.
   * Terapkan generic interceptors untuk memvalidasi token konteks metadata pada setiap RPC invocation.
   * Nonaktifkan gRPC Server Reflection pada exposed production build.

---

### 16. Hands-on Lab Step-by-Step

#### Step 1: Menyiapkan Lab Environment Terisolasi
Jalankan target API yang rentan (misalnya VAmPI - Vulnerable REST API) menggunakan Docker:

```bash
docker run -d --name vampi-target -p 5000:5000 erev0s/vampi
```

Verifikasi endpoint target berfungsi:
```bash
curl -I http://localhost:5000/
```

#### Step 2: Mengoperasikan Advanced API Fuzzing Menggunakan `ffuf`
Gunakan `ffuf` untuk memetakan endpoint yang tidak terdokumentasi dan mencari kerentanan parameter discovery.

Buat wordlist sederhana atau unduh SecLists:
```bash
echo -e "users\nadmin\ndebug\nv1\nv2\nconfig" > wordlist.txt
```

Jalankan Fuzzing untuk mendeteksi hidden API paths:
```bash
ffuf -w wordlist.txt -u http://localhost:5000/api/FUZZ \
     -mc 200,204,301,302,401,403 \
     -o ffuf_discovery_results.json
```

Fuzzing manipulasi ID numerik (indikator evaluasi BOLA):
```bash
ffuf -w <(seq 1 50) -u http://localhost:5000/users/v1/_debug/FUZZ \
     -mr "username" -o bola_probe_results.json
```

#### Step 3: Menjalankan OWASP ZAP API Scan Melalui CLI
Eksekusi pengujian otomatis berbasis skema OpenAPI dari VAmPI target:

```bash
docker run --rm -v $(pwd):/zap/wrk/:rw \
  zaproxy/zap-stable:2.14.0 zap-api-scan.py \
  -t http://172.17.0.1:5000/openapi/v1/spec.json \
  -f openapi \
  -r zap_vampi_report.html \
  -J zap_vampi_report.json
```
*(Catatan: `172.17.0.1` merujuk pada docker host IP gateway bridge).*

#### Step 4: Verifikasi dan Triase Hasil Scan
Ekstrak daftar kerentanan kritis yang teridentifikasi oleh ZAP:
```bash
jq '.site[].alerts[] | select(.riskcode == "3") | {vuln: .name, url: .instances[0].uri}' zap_vampi_report.json
```

---

### 17. Real-world Case Study & Incident Analysis Enterprise

* **Target Insiden:** Platform Ride-Sharing Skala Multinasional (2020).
* **Vektor Serangan:** Cacat Broken Object Level Authorization (OWASP API1:2023) pada Endpoint Pelacakan Perjalanan Driver.
* **Mekanisme Insiden:** Peneliti keamanan mengidentifikasi endpoint internal:
  `GET /api/v1/trips/{trip_uuid}/telemetry`
  Endpoint tersebut hanya memeriksa apakah penyerang memiliki token login aplikasi yang valid. Penyerang menukar `{trip_uuid}` dengan UUID trip acak milik pengemudi dan penumpang lain yang sedang berjalan.
* **Dampak Keamanan:** Data lokasi GPS real-time, nama lengkap pengemudi, riwayat transaksi pembayaran, dan identitas penumpang terekspos secara publik. Penyerang dapat melacak posisi fisik armada mobil secara serentak.
* **Kegagalan Pipeline SDLC:**
  1. Pengujian SAST tidak mendeteksi kegagalan otorisasi karena tidak ada signature sintaksis yang salah; fungsi `getTrip()` menerima parameter UUID dan mengeksekusi SQL query tanpa validasi relasi identitas.
  2. Baseline DAST scan standar yang dijalankan tim QA gagal menemukan bug tersebut karena tidak memiliki konfigurasi multi-identitas (*dual-persona role testing*).
* **Remediasi yang Diimplementasikan:**
  1. Penulisan kontrak otorisasi berbasis Open Policy Agent (OPA) / ABAC untuk memverifikasi apakah `trip.passenger_id == auth.subject.id` OR `trip.driver_id == auth.subject.id`.
  2. Implementasi skrip DAST kustom dalam CI/CD pipeline yang secara eksplisit menjalankan uji lintas identitas (*multi-context cross-account matrix scanning*).

---

### 18. Quiz Pemahaman & Challenge

#### Soal Konseptual & Analitikal
1. Mengapa memindai REST API menggunakan DAST konvensional (HTML Spider) menghasilkan cakupan *code coverage* yang sangat rendah, dan artefak apa yang harus disuplai ke DAST engine untuk mengatasinya?
2. Bagaimana mekanisme interaksi IAST agent di dalam runtime yang menyebabkannya memiliki rasio *false positive* jauh lebih rendah dibandingkan DAST black-box scanner murni?
3. Pada pengujian GraphQL, sebutkan dua vektor serangan DoS spesifik yang tidak umum ditemukan pada REST API tradisional!
4. Pipeline CI/CD Anda memicu fail-gate pada ZAP Active Scan karena deteksi SQLi berbasis waktu (*Time-based blind SQL Injection*). Namun, setelah diaudit, latensi tinggi tersebut disebabkan oleh database target yang sedang menjalankan transaksi locking secara bersamaan. Pendekatan arsitektur apa yang wajib diimplementasikan untuk memisahkan noise operasional ini?

#### Hands-on Challenge
* **Skenario:** Anda ditugaskan membangun pipeline DAST gating untuk arsitektur Microservices berbasis gRPC.
* **Tantangan:** Karena gRPC berkomunikasi menggunakan HTTP/2 dan protocol buffers biner terkompilasi, tuliskan konfigurasi bash/Docker script yang mengaktifkan perantara dynamic proxy (misal: Envoy atau `grpc-json-transcoder`) sehingga scanner REST DAST dapat menerjemahkan JSON payload menjadi gRPC call terfuzzing langsung ke pod target di pipeline CI/CD!

---

### 19. Summary & Key Takeaways
* DAST memvalidasi postur keamanan runtime aplikasi dan infrastruktur perimeternya dari sudut pandang adversary eksternal.
* Pengujian keamanan API modern membutuhkan parser berbasis skema formal (OpenAPI, GraphQL Schema, Protobuf Definitions); crawling konvensional tidak lagi memadai.
* OWASP API Security Top 10 didominasi oleh kelemahan otorisasi tingkat lanjut (BOLA, BFLA, BOPLA) yang membutuhkan strategi multi-context authentication testing.
* Fuzzing (`ffuf`, `wfuzz`) berfungsi mengisi ruang kosong yang terlewat oleh dokumen spesifikasi untuk mendeteksi *shadow endpoints* dan unhandled exception logic.
* Mengintegrasikan DAST ke dalam pipeline CI/CD menuntut isolasi target pada container ephemeral, mitigasi state mutation, serta evaluasi gate threshold berbasis tingkat keparahan risiko (CVSS).

---

### 20. Referensi Resmi & Standar Keamanan
* **OWASP Foundation:**
  * [OWASP API Security Top 10 (2023 Standard)](https://owasp.org/www-project-api-security/)
  * [OWASP Zed Attack Proxy (ZAP) CI/CD Integration Guide](https://www.zaproxy.org/docs/docker/api-scan/)
* **NIST Special Publications:**
  * NIST SP 800-115: *Technical Guide to Information Security Testing and Assessment*, Seksi 5.3 (Dynamic Analysis).
  * NIST SP 800-53 Rev. 5: Kontrol Keamanan CA-8 (Penetration Testing) dan RA-5 (Vulnerability Scanning).
* **MITRE ATT&CK Matrix:**
  * Tactic: Initial Access (TA0001) – Exploit Public-Facing Application (T1190).
* **CIS Controls:**
  * CIS Control 16: *Application Software Security* (16.12: Perform Dynamic Application Security Testing).