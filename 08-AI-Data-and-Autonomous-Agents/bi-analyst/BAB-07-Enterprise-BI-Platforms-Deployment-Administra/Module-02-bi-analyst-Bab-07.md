# BAB 07: Enterprise BI Platforms Deployment & Administration
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengoperasikan arsitektur enterprise Business Intelligence (BI) multi-region yang berdaya tahan tinggi (*high-availability*) dan scalable.
- Mengimplementasikan metodologi **BI-as-Code** menggunakan format deklaratif (misal: Fabric/Power BI Developer Mode `.pbip`, Tabular Model Definition Language/TMDL, atau Looker LookML) yang terintegrasi penuh ke pipeline CI/CD (GitHub Actions / Azure DevOps).
- Mengonfigurasi arsitektur **Enterprise On-Premises Data Gateway** berkonsep *high-availability cluster* dengan load balancing dan network isolation.
- Menerapkan tata kelola keamanan granular tingkat lanjut: Row-Level Security (RLS) dinamis, Object-Level Security (OLS), integrasi identity management (Microsoft Entra ID / Okta), serta isolasi multi-tenant.
- Mendiagnosis dan mengoptimalkan performa kapasitas (*capacity sizing*, memory throttling, concurrency limits) dan menyusun strategi Disaster Recovery (RPO < 1 jam, RTO < 4 jam) untuk platform BI enterprise.

---

### 2. Prerequisite
Untuk mengikuti modul ini dengan optimal, peserta wajib menguasai:
- **Foundational BI Administration**: Pemahaman arsitektur dasar workspace/site, tenant, lisensi (misal: Power BI Pro vs. Premium/Fabric F-SKU, Tableau Creator vs. Viewer).
- **Advanced Data Modeling**: Penguasaan skema Star/Snowflake, kalkulasi analitik (DAX lanjutan atau SQL Window Functions), serta evaluasi query plan / execution metrics.
- **DevOps & Infrastructure**: Pengalaman dasar menggunakan Git, YAML pipeline syntax, Linux bash/shell scripting, serta pemahaman jaringan enterprise (VNet, Private Link, Reverse Proxy, Firewall Rules).
- **Identity & Access Management (IAM)**: Pemahaman protokol OAuth 2.0, SAML 2.0, Service Principal/Managed Identity, dan konsep Role-Based Access Control (RBAC).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi BI enterprise modern memisahkan platform menjadi tiga layer arsitektural terisolasi: **Control Plane**, **Data/Semantic Engine Plane**, dan **Data Ingestion & Connectivity Plane**.

```
+-----------------------------------------------------------------------+
|                            CONTROL PLANE                              |
|  - Entra ID / Okta (RBAC & Auth)       - Tenant Settings & Governance  |
|  - Deployment Pipelines Engine         - Audit Logs / Activity APIs   |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                     DATA / SEMANTIC ENGINE PLANE                      |
| +-------------------------------------------------------------------+ |
| | VertiPaq / Tabular Engine / Hyper Engine / Looker In-Memory      | |
| | - Memory Allocator & Paging          - Query Processor & Formula  | |
| | - Dynamic Cache Management          - Row/Object-Level Security   | |
| +-------------------------------------------------------------------+ |
| | DirectLake / DirectQuery / Live Connection Routing Engine         | |
| +-------------------------------------------------------------------+ |
+-----------------------------------------------------------------------+
                                  ^
                                  | (TLS 1.3 / Azure Service Bus)
+-----------------------------------------------------------------------+
|                DATA INGESTION & CONNECTIVITY PLANE                    |
| +-------------------------------------------------------------------+ |
| | Enterprise Gateway Cluster                                        | |
| | Node 1 (Active) <---> Node 2 (Active) <---> Node 3 (Spool/Failover) |
| | - Spool Storage Engine               - DirectQuery Connection Pool| |
| +-------------------------------------------------------------------+ |
| | Private Endpoints (Azure Private Link / AWS PrivateLink)          | |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| SOURCE SYSTEMS (Snowflake, Databricks, On-Premises DW, Cloud Storage) |
+-----------------------------------------------------------------------+
```

#### A. Semantic Engine Internals (VertiPaq / Memory Management)
Ketika model data dideploy ke shared capacity atau dedicated capacity (misal: Power BI Premium F64 atau Tableau Server Core):
1. **Dictionary Encoding & Bit-packing**: VertiPaq membaca kolom sumber, membuat kamus integer yang dipetakan ke nilai riil (menurunkan footprint string), dan menyusun data per baris ke format berorientasi kolom (*columnar storage*).
2. **Paging & Throttling Limits**: Jika batas alokasi memori fisik per model terlampaui (misal: 10 GB limit untuk dataset tunggal), engine mengeksekusi mekanisme eviksi LRU (*Least Recently Used*) atau melakukan kompresi ulang partisi dingin. Jika beban CPU kapasitas menyentuh ambang batas 100%, sistem menerapkan algoritma *interactive request delaying* (throttling) guna mempertahankan stabilitas *background jobs* (refresh data).
3. **Storage Engine (SE) vs. Formula Engine (FE)**: SE bersifat multi-threaded dan bekerja langsung pada data terkompresi di RAM; FE bersifat single-threaded, mengeksekusi kalkulasi kompleks (seperti iterasi baris non-linier). Arsitektur produksi harus memaksimalkan operasi di SE guna menghindari bottleneck di FE.

#### B. Enterprise Data Gateway Architecture
Gateway bertindak sebagai agen proksi reverse-proxy yang berdiri di dalam perimeter jaringan privat organisasi:
- Komunikasi bersifat **outbound only** melalui port HTTPS (443) ke Azure Service Bus / Cloud Message Broker. Tidak ada port inbound yang dibuka pada firewall internal.
- Konfigurasi **High Availability (HA) Gateway Cluster**: Terdiri dari kumpulan instans gateway fisik/VM. Beban dialihkan ke instans lain jika salah satu node gagal merespons heartbeat, atau didistribusikan menggunakan policy load-balancing berbasis resource (CPU, memory, concurrent queries limit).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Desktop-Centric) | Pendekatan Enterprise BI-as-Code |
| :--- | :--- | :--- |
| **Format File** | Binary opaque blobs (`.pbix`, `.twbx`) | Plain text / Declarative metadata (`.pbip`, TMDL, LookML) |
| **Kolaborasi Tim** | Pengembang saling menimpa file di network share | Version control berbasis Git, branching, peer review, pull request |
| **Deployment** | Upload manual via Web UI oleh analis | Pipeline otomatis (CI/CD) dengan validasi sintaks dan tes performa |
| **Manajemen Akses** | Hardcoded user list, manual permission sharing | Dynamic RLS berbasis Token Claims / Entra ID Security Groups & OLS |
| **Disaster Recovery** | Bergantung pada backup manual analis | Disaster Recovery terotomatisasi dengan IaC (Terraform) dan metadata backup |

#### Mengapa BI-as-Code Wajib di Skala Enterprise?
1. **Auditability & Traceability**: Setiap perubahan rumus bisnis (kalkulasi margin, revenue) terlacak dalam Git commit history beserta autor dan approval log.
2. **Deterministic Releases**: Menghilangkan inkonsistensi antara environment Development, Staging (UAT), dan Production.
3. **Decoupled Architecture**: Memisahkan layer visualisasi UI dari layer model semantik. Tim data engineer fokus pada optimasi model, sedangkan tim analis fokus pada visualisasi tanpa benturan file lock.

---

### 5. How (Workflow Detail)

Siklus hidup rilis platform BI enterprise mengikuti standar rekayasa perangkat lunak modern:

```
[Developer Branch]
       |
       v (Commit .pbip / TMDL)
[Pull Request to Main] ---> [Automated Semantic Linter (PBIX Inspector / Tabular Guard)]
       |                    [BPA Rules Verification via CLI]
       v (Merged)
[CI Pipeline: Staging] ---> [Deploy to UAT Workspace via REST API / XMLA Endpoint]
       |                    [Trigger Data Refresh on UAT Data Warehouse]
       |                    [Execute Automated DAX Query Performance Benchmark]
       v (Approved)
[CD Pipeline: Production] -> [Blue/Green Swap or Direct Production Workspace Update]
                            [Set Service Principal Permissions & Apply OLS/RLS Rules]
                            [Run Post-Deploy Smoke Tests]
```

Langkah teknis implementasi:
1. **Ekstraksi Definisi Metadata**: Model didefinisikan dalam format terdekonstruksi (`model.tmdl`, `database.json`, dsb.).
2. **Automated Static Code Analysis**: Menguji model terhadap best practice rules (misal: tidak boleh ada relasi bi-directional non-deterministik, kolom tipe data integer tanpa format string, kalkulasi tanpa skema partisi eksplisit).
3. **Deployment via Headless CLI**: Menggunakan endpoint XMLA (protokol MS-SSAS) atau Public REST API dari platform BI untuk menyuntikkan model langsung ke kapasitas tenant tanpa memerlukan interaksi GUI.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan platform BI enterprise seperti **Jaringan Maskapai Penerbangan Modern**:
- **Semantic Model (Dataset)** adalah *Pesawat*: Harus dirawat secara presisi, kapasitas bobot (RAM) dibatasi secara ketat, dan rutenya (jalur kueri) harus dioptimalkan.
- **Enterprise Gateway** adalah *Terowongan Boarding Terproteksi*: Menghubungkan area terminal publik/cloud dengan hanggar pesawat privat/on-premise secara terisolasi tanpa ada celah penyusup masuk dari luar.
- **CI/CD BI Pipeline** adalah *ATC & Sistem Navigasi Otomatis*: Mengatur pesawat mana yang boleh lepas landas (deploy), menguji kelaikan terbang sebelum memasuki jalur penerbangan utama (production), dan membatalkan penerbangan jika cuaca/kualitas kode buruk.

#### Diagram Topologi Produksi
```
  [ ANALYTICS CONSUMERS ]
         |
         | (HTTPS / OAuth2 Token with Entra ID Claims)
         v
+--------------------------------------------------------------------------+
| BI CLOUD SERVICE TENANT (MULTI-REGION / DEDICATED CAPACITY)              |
|                                                                          |
|  [ Dev Workspace ] ----> [ Test Workspace ] ----> [ Prod Workspace ]    |
|                                                          |               |
|                                            +-------------+-------------+ |
|                                            | DirectQuery / DirectLake  | |
|                                            | or Scheduled Refresh      | |
+--------------------------------------------+-------------+---------------+
                                                           |
                          +--------------------------------+
                          | (Encrypted TLS 1.3 Outbound)
                          v
        +-----------------------------------+
        | ON-PREMISES DATA GATEWAY CLUSTER  |
        | (DMZ / Private Virtual Network)   |
        |                                   |
        |  [Node 1: Primary VM]             |
        |  [Node 2: Active Load VM]         |
        |  [Node 3: Standby VM]             |
        +-----------------+-----------------+
                          |
             (Kerberos Constrained Delegation / Private Link)
                          v
        +-----------------------------------+
        | ENTERPRISE DATA SOURCES           |
        | - Enterprise Data Warehouse       |
        | - Operational Read-Replicas       |
        +-----------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Dynamic Row-Level Security (DAX)
Implementasi filter keamanan berbasis user session aktif menggunakan kombinasi User Principal Name (UPN) dan pemetaan security group.

```dax
-- Tabel: SecurityMapping
-- Kolom: UserEmail, DepartmentKey, RegionKey

-- Expression RLS pada Tabel 'DimDepartment'
[DepartmentKey] IN (
    CALCULATETABLE(
        SecurityMapping[DepartmentKey],
        SecurityMapping[UserEmail] = USERPRINCIPALNAME()
    )
)
||
-- Master Admin Override (Group bypass)
USERPRINCIPALNAME() IN { "bi-admin@enterprise.domain" }
```

#### B. Practical Example: Production CI/CD Deployment Script (GitHub Actions + Tabular Editor CLI)
Pipeline ini melakukan validasi linting Best Practice Analyzer (BPA) pada metadata model analitik (TMDL/TMSL) dan mendeploy-nya langsung ke workspace target menggunakan Service Principal via XMLA Endpoint.

```yaml
name: Deploy Semantic Model to Production

on:
  push:
    branches:
      - main
    paths:
      - 'semantic-models/**'

env:
  TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
  CLIENT_ID: ${{ secrets.AZURE_SPN_CLIENT_ID }}
  CLIENT_SECRET: ${{ secrets.AZURE_SPN_CLIENT_SECRET }}
  WORKSPACE_CONNECTION: "powerbi://api.powerbi.com/v1.0/myorg/BI_Production_Workspace"
  DATASET_NAME: "Enterprise_Sales_Analytics"

jobs:
  validate-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Install Tabular Editor 3 CLI
        run: |
          wget https://cdn.tabulareditor.com/files/TabularEditor.3.Package.Linux.latest.deb
          sudo dpkg -i TabularEditor.3.Package.Linux.latest.deb

      - name: Run Best Practice Analyzer (BPA) Check
        run: |
          # Evaluasi model terhadap file rules BPA industri
          te3 semantic-models/SalesModel \
            --analyzer semantic-models/bpa-rules.json \
            --fail-on-error

      - name: Deploy Model via XMLA Endpoint
        run: |
          # Eksekusi deployment deklaratif menggunakan Tabular Editor CLI
          te3 semantic-models/SalesModel \
            --deploy "$WORKSPACE_CONNECTION" "$DATASET_NAME" \
            --credential-type ServicePrincipal \
            --tenant "$TENANT_ID" \
            --username "$CLIENT_ID" \
            --password "$CLIENT_SECRET" \
            --mode DeployMetadataOnly

      - name: Post-Deployment Smoke Test (Direct Query Trigger via Python)
        run: |
          python3 -m pip install msal requests
          python3 scripts/trigger_refresh_and_smoke_test.py \
            --tenant-id "$TENANT_ID" \
            --client-id "$CLIENT_ID" \
            --client-secret "$CLIENT_SECRET" \
            --workspace "BI_Production_Workspace" \
            --dataset-name "$DATASET_NAME"
```

Skrip Python (`scripts/trigger_refresh_and_smoke_test.py`) untuk inisiasi refresh asinkronus dan pengecekan kesehatan:

```python
import argparse
import sys
import time
import requests
import msal

def get_bearer_token(tenant_id, client_id, client_secret):
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["https://analysis.windows.net/powerbi/api/.default"]
    app = msal.ConfidentialClientApplication(
        client_id, authority=authority, client_credential=client_secret
    )
    result = app.acquire_token_for_client(scopes=scope)
    if "access_token" in result:
        return result["access_token"]
    raise RuntimeError(f"Authentication failed: {result.get('error_description')}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--dataset-name", required=True)
    args = parser.parse_args()

    token = get_bearer_token(args.tenant_id, args.client_id, args.client_secret)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Dapatkan Dataset ID
    groups_url = "https://api.powerbi.com/v1.0/myorg/groups"
    res = requests.get(groups_url, headers=headers).json()
    group_id = next((g["id"] for g in res["value"] if g["name"] == args.workspace), None)
    if not group_id:
        sys.exit(f"Workspace {args.workspace} tidak ditemukan.")

    datasets_url = f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets"
    ds_res = requests.get(datasets_url, headers=headers).json()
    dataset_id = next((d["id"] for d in ds_res["value"] if d["name"] == args.dataset_name), None)
    if not dataset_id:
        sys.exit(f"Dataset {args.dataset_name} tidak ditemukan.")

    # Trigger Refresh
    refresh_url = f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/datasets/{dataset_id}/refreshes"
    post_res = requests.post(refresh_url, headers=headers, json={"type": "Full"})
    if post_res.status_code != 202:
        sys.exit(f"Gagal memicu refresh: {post_res.text}")

    print(f"Refresh asinkronus berhasil dipicu untuk dataset ID: {dataset_id}")

if __name__ == "__main__":
    main()
```

---

### 8. Real World Case Study (Enterprise Scale)

**Konteks**: Lembaga Perbankan Finansial Tier-1 melayani 15 juta nasabah dengan 8.000 internal analytics consumer.  
**Tantangan**:
- Terjadi insiden kepatuhan data: Analis cabang dapat melihat ringkasan omzet regional cabang lain karena logika filter manual di dashboard.
- Downtime harian selama 2 jam pada pukul 08:00 AM saat ribuan manager cabang login bersamaan, menyebabkan VertiPaq memory crash pada server (OOM Throttling).
- Pembaruan metrik analitik membutuhkan siklus 4 minggu karena proses pengujian manual dan file `.pbix` seukuran 12 GB.

**Arsitektur Solusi Rekayasa**:
1. **Migrasi ke DirectLake + Lakehouse Partitioning**: Model berpindah dari Full Import 12 GB ke direct reading format delta-parquet terkompresi melalui Delta Engine. Memory footprint berkurang sebesar 82%.
2. **Dynamic Entra ID Claims Mapping**:
   - Dibuat Object-Level Security (OLS) untuk menyembunyikan kolom sensitif (`CustomerPII`, `TaxNumber`).
   - Menerapkan Dynamic RLS yang membaca JWT security claim langsung dari sesi autentikasi pengguna:
     ```dax
     [Branch_Code] = LOOKUPVALUE(
         DimUserAccess[Branch_Code],
         DimUserAccess[UserPrincipalName], USERPRINCIPALNAME()
     )
     ```
3. **Gateway Clustering**: Membangun 4 node VM on-premises Gateway di belakang Azure Internal Load Balancer dengan bandwidth dedicated 10 Gbps ExpressRoute.
4. **Git Integration & CI/CD**:
   - Format biner dihapus; beralih ke `.pbip` yang disimpan di Azure DevOps Repos.
   - Lead architect memverifikasi setiap PR melalui pipeline otomasi yang memvalidasi kepatuhan RLS sebelum merge ke branch `main`.

**Hasil & Metrik Produksi**:
- Incident data leakage turun menjadi **0**.
- P95 visual render time turun dari **24.5 detik** menjadi **1.2 detik**.
- Waktu deployment metrik baru dipangkas dari **28 hari** menjadi **45 menit** dengan nol downtime.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                           [Data Import (VertiPaq)]
                                     / \
                                    /   \
                                   /     \
                                  /       \
  [DirectLake / Hybrid] <-------+---------+-----> [DirectQuery / Live Connection]
```

| Parameter | Mode Import (VertiPaq Cache) | DirectQuery / Live Connection | Mode DirectLake (Modern Enterprise) |
| :--- | :--- | :--- | :--- |
| **Query Performance** | **Tertinggi**: Data berada langsung dalam in-memory columnar database. | **Rendah - Sedang**: Tergantung load dan performa underlying source database. | **Hampir Setara Import**: Membaca langsung cold cache Delta Parquet ke memory. |
| **Data Freshness / Latency** | **Terjadwal**: Mengharuskan refresh batch (interval 15-60 menit). | **Real-time**: Kueri dieksekusi langsung ke source saat visual dirender. | **Near Real-time**: Hanya memperbarui delta framing pointer file parquet. |
| **Capacity Memory Footprint** | **Tinggi**: Seluruh data tersimpan di RAM kapasitas BI. | **Nol / Minimal**: Hanya metadata yang dimuat dalam memory platform BI. | **Adaptif**: Model memanfaatkan paging memory berbasis konsumsi kueri. |
| **Source Engine Overhead** | **Rendah**: Hanya membebani source saat siklus refresh terjadwal. | **Sangat Tinggi**: Kueri masif ribuan user memicu spike di data warehouse. | **Nol**: Membaca storage layer secara langsung tanpa compute cluster database. |
| **Biaya Infrastruktur** | Memerlukan SKU kapasitas memori besar (P2/F128 ke atas). | Membutuhkan DW compute cluster yang menyala terus menerus. | Biaya komputasi seimbang; efisiensi tinggi pada arsitektur OneLake. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum Produksi
1. **Bi-Directional Cross-Filtering pada Cardinality Tinggi**:
   - *Problem*: Mengaktifkan relasi dua arah pada tabel fakta dengan jutaan baris menghasilkan looping query plan dan kehabisan memori.
   - *Solusi*: Pertahankan relasi single direction; gunakan kalkulasi `CALCULATE(..., CROSSFILTER(...))` hanya ketika diperlukan secara lokal.
2. **Ketergantungan pada Single-Node Gateway**:
   - *Problem*: Gateway VM crash atau pending OS update menyebabkan seluruh scheduled refresh dan DirectQuery dashboard gagal total.
   - *Solusi*: Pasang minimal 2 node dalam satu Gateway Cluster dengan mode load balancing aktif.
3. **Penyalahgunaan Fungsi RLS Non-Deterministik**:
   - *Problem*: Menempatkan kalkulasi RLS rumit dengan fungsi skalar non-evaluatif seperti `PATHCONTAINS` tanpa membuat indexed bridge table terlebih dahulu.
   - *Solusi*: Buat relasi struktural denormalisasi khusus hak akses yang diproses di level ETL/ELT data warehouse sebelum masuk ke semantic model.

#### Prosedur Troubleshooting Insiden
- **Gejala: Error "Capacity Limit Exceeded / CPU Throttling"**
  1. Buka Capacity Metrics App / Performance Profiler log.
  2. Identifikasi Query Hash dengan metrik CPU Time (ms) tertinggi.
  3. Periksa apakah ada background refresh yang berjalan berbarengan dengan peak interactive consumption hours (09:00 - 11:00).
  4. Lakukan rescheduling background jobs ke off-peak hours atau alokasikan workload pool tersendiri.
- **Gejala: Gateway Mashup Engine "Out of Memory" Error**
  1. Buka file konfigurasi `Microsoft.PowerBI.DataMovement.Pipeline.GatewayCore.dll.config` pada server Gateway.
  2. Modifikasi atribut `StreamBeforeRequestCompletes` menjadi `True`.
  3. Naikkan parameter `MashupDisableChunkedQueryExecution` atau set batas `MashupDefaultPoolContainerMaxCount` sesuai core fisik VM.
  4. Restart Windows Service Gateway.

---

### 11. Best Practices (Production Checklist)

- [ ] **Declarative Git Versioning**: Semua model semantik wajib menggunakan format dekonstruksi (`.pbip` / TMDL / LookML) dan disimpan di Git repo dengan branch protection enabled.
- [ ] **Zero Hardcoded Secrets**: Tidak boleh ada database connection string, password, atau master key di dalam file metadata. Wajib menggunakan Entra ID Service Principal atau Azure Key Vault references.
- [ ] **Isolated Capacities**: Pisahkan workspace Development/Test dari Workspace Production pada level Dedicated Capacity (hindari Dev model menghabiskan CPU allocation model operasional).
- [ ] **Gateway Health Monitoring**: Alerting otomatis berbasis webhook/Slack/Teams aktif jika heartbeat salah satu node Gateway mati selama lebih dari 3 menit.
- [ ] **Row-Level Security Hardening**: Test evaluasi akun non-admin via impersonation tool ("Test as Role") wajib dijalankan di CI sebelum merge ke branch `main`.
- [ ] **Storage Partitioning**: Dataset di atas 50 juta baris wajib dipartisi secara vertikal/horizontal (misal: Partisi per Tahun/Bulan) dengan memanfaatkan Incremental Refresh Policy.
- [ ] **OLS Compliance**: Kolom berisi data PII atau metrik gaji pegawai disembunyikan menggunakan Object-Level Security (OLS) dari role default viewer.

---

### 12. Hands-on Practice

Buat dan simpan seluruh artefak praktikum ini di direktori: `hands-on/m02/`

#### Skenario
Anda diminta menyiapkan fondasi deployment otomatis untuk model semantik `EnterpriseSales` menggunakan Azure DevOps / Bash script, lengkap dengan aturan Best Practice Analyzer (BPA) dan simulasi clustering Gateway.

#### Langkah Praktikum

##### Langkah 1: Siapkan Struktur Repositori Model
Buka terminal dan bangun direktori berikut:
```bash
mkdir -p hands-on/m02/{config,scripts,semantic-model,rules}
cd hands-on/m02
```

##### Langkah 2: Buat Definisi Rule Best Practice Analyzer (BPA)
Simpan file berikut di `rules/bpa-rules.json`. File ini akan mendeteksi anti-pattern arsitektur BI:
```json
[
  {
    "ID": "RULE_NO_DIRECT_RELS_ON_BOTH_DIRECTIONS",
    "Name": "Hindari Cross-filtering Bi-directional",
    "Category": "Performance",
    "Severity": 1,
    "Scope": "Relationship",
    "Expression": "CrossFilteringBehavior == CrossFilteringBehavior.BothDirections"
  },
  {
    "ID": "RULE_UNHIDDEN_FOREIGN_KEYS",
    "Name": "Kunci Relasi Wajib Disembunyikan dari Reporting",
    "Category": "Design",
    "Severity": 2,
    "Scope": "Column",
    "Expression": "Name.EndsWith(\"Key\") and IsHidden == false"
  }
]
```

##### Langkah 3: Buat Mock Skrip Validator Deklaratif (Linter)
Simpan file berikut di `scripts/lint_model.py`. Skrip ini bertindak sebagai validation gatekeeper di CI pipeline:
```python
import json
import os
import sys

def lint_model():
    print("[INFO] Memulai Semantic Model Governance Linting...")
    rules_file = "rules/bpa-rules.json"
    
    if not os.path.exists(rules_file):
        print(f"[ERROR] Rule file {rules_file} tidak ditemukan!")
        sys.exit(1)

    with open(rules_file, "r") as f:
        rules = json.load(f)

    # Mock schema data yang didapat dari branch git
    mock_model_schema = {
        "tables": [
            {
                "name": "FactSales",
                "columns": [
                    {"name": "CustomerKey", "isHidden": False},
                    {"name": "Revenue", "isHidden": False}
                ]
            }
        ],
        "relationships": [
            {
                "fromTable": "FactSales",
                "toTable": "DimCustomer",
                "crossFilteringBehavior": "BothDirections"
            }
        ]
    }

    violations = []

    # Validasi Relationship Rule
    for rel in mock_model_schema["relationships"]:
        if rel["crossFilteringBehavior"] == "BothDirections":
            violations.append(f"[SEV 1] Relasi {rel['fromTable']} -> {rel['toTable']} melanggar: Bi-directional filtering terdeteksi!")

    # Validasi Column Rule
    for table in mock_model_schema["tables"]:
        for col in table["columns"]:
            if col["name"].endswith("Key") and not col["isHidden"]:
                violations.append(f"[SEV 2] Kolom {table['name']}[{col['name']}] melanggar: Foreign Key harus disembunyikan!")

    if violations:
        print("[FAILED] Model melanggar tata kelola produksi:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    print("[SUCCESS] Model lolos semua pengujian Best Practice Analyzer.")

if __name__ == "__main__":
    lint_model()
```

##### Langkah 4: Eksekusi dan Verifikasi
Jalankan linter untuk memverifikasi proteksi pipeline:
```bash
python3 scripts/lint_model.py
```
*Amati error yang muncul. Ubah skema mock di file Python agar kolom `CustomerKey` berstatus `isHidden: True` dan ubah relasi menjadi `SingleDirection`, kemudian jalankan kembali hingga lolos.*

---

### 13. Exercise

#### Level Easy
Buat ekspresi DAX untuk Row-Level Security sederhana di mana user yang berasal dari unit bisnis 'Logistics' hanya dapat membaca data yang status transaksinya bukan 'Draft'.
- Input: Tabel `Orders` dengan kolom `OrderCategory` dan `Status`.
- Ekspektasi output: Logic boolean DAX yang valid.

#### Level Medium
Sebuah instans Gateway cluster menunjukkan penggunaan CPU 98% pada Node 1 sedangkan Node 2 hanya 15%. Rancang skrip PowerShell atau file konfigurasi XML untuk memodifikasi threshold concurrency agar gateway mendistribusikan kueri secara berimbang (*resource-based balancing*).

#### Level Hard
Rancang pipeline architecture blue/green deployment zero-downtime untuk dataset berukuran 500 GB di DirectLake/Analysis Services. Sertakan mekanisme rollback otomatis jika terjadi degradasi performa p95 visual latency melebihi 3 detik dalam 10 menit pasca deployment.

---

### 14. Challenge

**Skenario Tantangan Riil (Merger & Acquisition Multi-Cloud)**:  
Perusahaan Anda baru saja mengakuisisi kompetitor ritel global. 
- **Entitas A (Induk)**: Berjalan di Power BI Dedicated Capacity (F128) di Microsoft Azure (Region US-East).
- **Entitas B (Anak Usaha)**: Berjalan di Tableau Server on-premises yang terhubung ke Snowflake di AWS (Region EU-Central).
- **Kebutuhan**: Dewan Direksi membutuhkan satu Semantic Layer terkonsolidasi yang dapat diakses oleh kedua entitas dengan aturan:
  1. Single Sign-On menggunakan Entra ID induk.
  2. Data resident ritel anak usaha **tidak boleh keluar** dari wilayah legal teritorial Uni Eropa (GDPR boundary).
  3. Latensi rendering visual tidak boleh melampaui ambang 2.5 detik untuk 5.000 user konkuren di seluruh dunia.
  4. Pengelolaan skema harus deklaratif penuh (BI-as-Code) yang dikendalikan satu tim platform engineer terpusat.

**Tugas Anda**: Buat dokumen Blueprint Arsitektur Komprehensif (disertai Diagram Komponen ASCII, Alur Data, Desain Gateway/Private Endpoint, Model Partisi, dan Pipeline Release) yang memecahkan masalah di atas secara deterministik tanpa melanggar batasan regulasi data.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa fungsi utama dari VertiPaq Storage Engine dibandingkan Formula Engine pada arsitektur semantic model tabular?
2. Mengapa port inbound tidak perlu dibuka pada firewall internal saat menginstal Enterprise On-Premises Data Gateway?
3. Sebutkan perbedaan mendasar antara Row-Level Security (RLS) dan Object-Level Security (OLS).
4. Apa kelemahan utama menyimpan model semantik enterprise dalam format file biner tunggal (misal `.pbix`) dibandingkan format deklaratif (seperti `.pbip`/TMDL)?
5. Pada kondisi apa strategi deployment model semantik memerlukan alokasi endpoint XMLA baca/tulis (*read-write*)?

#### B. Pertanyaan Intermediate
6. Bagaimana cara kerja algoritma *throttling* pada shared atau dedicated BI capacity saat terjadi pemakaian CPU mencapai 100% secara beruntun?
7. Jelaskan alur resolusi query pada mode hybrid dataset yang menggabungkan partisi Import (historis) dan partisi DirectQuery (hari berjalan).
8. Mengapa fungsi DAX seperti `USEROBJECTID()` atau `USERPRINCIPALNAME()` menghasilkan evaluasi dinamis yang membatalkan optimasi pre-computed cache?
9. Bagaimana langkah konfigurasi high-availability cluster gateway untuk mencegah *single point of failure* jika salah satu server host mengalami mati listrik mendadak?
10. Dalam siklus release CI/CD, parameter apa yang membedakan mode deployment `DeployMetadataOnly` dengan Full Deployment beserta data storage-nya?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Setelah melakukan deployment model semantik baru ke production workspace, rata-rata konsumsi memori melonjak dari 15 GB menjadi 85 GB secara drastis padahal jumlah baris data sumber hanya bertambah 2%. Apa akar masalah teknis yang paling mungkin terjadi di level internal VertiPaq engine, dan bagaimana cara memverifikasinya?
12. **Skenario 2**: Perusahaan mengaktifkan Dynamic RLS berbasis tabel pemetaan pengguna (`UserAccessMapping`). Namun, saat 2.000 pengguna mengakses dashboard secara serentak pada Senin pagi, query latency naik tajam hingga 45 detik per visual. Analisis letak inefisiensi arsitektural RLS tersebut dan berikan solusi optimasinya.
13. **Skenario 3**: Sebuah proses automated pipeline men-deploy perubahan skema tabel ke Production via API. Refresh data berhasil, tetapi semua dashboard visual consumer menampilkan status error: *"The field 'X' has been removed or renamed"*. Bagaimana Anda mendesain validation contract testing di CI pipeline guna menjamin breaking changes semacam ini tertangkap sebelum masuk ke tahap production workspace deployment?

---

### 16. Summary

- **Modern BI Architecture** telah berevolusi dari artefak desktop monolitik berbasis biner menuju model terdistribusi, terkelola, dan otomatis (**BI-as-Code**).
- Format deklaratif (seperti `.pbip`, TMDL, LookML) memungkinkan penerapan disiplin rekayasa perangkat lunak mapan: Git branching, code review, static analysis (BPA), serta integrasi pipeline CI/CD zero-downtime.
- **Enterprise Data Gateway** wajib dirancang dalam topologi cluster high-availability dengan konfigurasi load balancing adaptif guna memastikan kesinambungan transfer data terenkripsi melintasi perimeter jaringan privat ke cloud.
- Tata kelola keamanan produksi mensyaratkan isolasi data terperinci melalui Dynamic Row-Level Security (RLS) deterministik dan Object-Level Security (OLS) yang terikat langsung ke token claims identitas perusahaan (Entra ID/Okta).
- Pemilihan mode konektivitas (Import, DirectQuery, DirectLake) merupakan kompromi antara performa kueri, batas latensi data, footprint memori, serta beban pada underlying compute infrastructure. Arsitek BI enterprise harus mampu menyeimbangkan seluruh parameter ini secara presisi.