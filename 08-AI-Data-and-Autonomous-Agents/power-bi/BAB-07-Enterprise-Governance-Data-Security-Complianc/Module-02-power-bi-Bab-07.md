# BAB 07: Enterprise Governance, Data Security & Compliance
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonfigurasi arsitektur keamanan tingkat lanjut pada Power BI/Fabric Semantic Models, mencakup Dynamic Row-Level Security (RLS) berbasis relasi rekursif (hierarki organisasi) dan Object-Level Security (OLS) menggunakan Tabular Model Definition Language (TMDL) / Tabular Model Scripting Language (TMSL).
- Mengimplementasikan isolasi jaringan privat perusahaan memanfaatkan Azure Private Link, Managed Virtual Network (VNet) Data Gateway, dan Service Endpoints untuk mencegah kebocoran data (*data exfiltration*).
- Mengotomatisasi tata kelola (*governance audit*) dan siklus rilis *artifacts* berbasis Service Principal menggunakan Power BI REST APIs, Fabric Admin APIs, dan Azure DevOps/GitHub Actions pipelines.
- Mengintegrasikan Microsoft Purview Information Protection untuk klasifikasi sensitivitas data (*sensitivity labels*), enkripsi *end-to-end*, dan evaluasi kepatuhan (*compliance*) lintas batas regulasi (GDPR, HIPAA, OJK/PDP).

---

### 2. Prerequisite

Untuk menguasai materi ini secara optimal, peserta wajib memahami:
- Arsitektur internal Analysis Services VertiPaq Engine (kamus kompresi, hierarki memori, dan propagasi filter konteks).
- Penguasaan bahasa DAX tingkat lanjut (*evaluation contexts*, context transition, iterator functions, dan ekspresi tabel).
- Pengalaman administrasi Microsoft Entra ID (sebelumnya Azure AD): konfigurasi Security Groups, Service Principals (App Registrations), dan skema autentikasi OAuth 2.0 / Certificate-based authentication.
- Pemahaman protokol jaringan enterprise: CIDR notation, Subnetting, Azure Virtual Network, Hub-and-Spoke Topology, dan TLS/Kerberos Constrained Delegation.
- Lisensi aktif: Power BI Premium Per Capacity (P-SKU) atau Fabric Capacity (F-SKU) untuk eksekusi fitur XMLA Read/Write, OLS, dan Deployment Pipelines.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Mekanisme Resolusi Identitas VertiPaq & RLS Query Rewrite
Saat visual pada laporan Power BI memicu sebuah DAX Query, engine VertiPaq tidak menjalankan kueri dalam konteks data mentah terbuka. Jika Semantic Model memiliki aturan Dynamic RLS:
1. **Identitas Pengguna**: VertiPaq menangkap token otentikasi pengakses via Microsoft Entra ID dan mengekstrak klaim identitas, umumnya dipetakan ke fungsi `USERPRINCIPALNAME()` (format: `user@domain.com`) atau `USERNAME()` (Domain\User atau SID).
2. **DAX Sub-expression Injection**: Formula predicate RLS yang didefinisikan pada tabel tertentu (misal: tabel `DimUserSecurity`) diinjeksikan secara transparan ke dalam blok `FILTER()` internal kueri.
3. **Internal Filtering Graph**: VertiPaq Engine mengaplikasikan ekspresi RLS sebagai filter kontekstual baris dasar (*row filter*). Data yang tidak lolos predikat *boolean* dipangkas (*pruned*) dari *in-memory segment storage* sebelum kalkulasi agregasi (*Hash Aggregations* atau *Sort Aggregations*) dieksekusi. 

```
[DAX Query dari Visual]
         │
         ▼
[VertiPaq Formula Engine] ──(Inject Predicate Dynamic RLS via TMDL/TMSL)
         │
         ▼
[VertiPaq Storage Engine] ──(Pruning Bitmaps / Bit-slice indexing)
         │
         ▼
[Evaluated Safe Data Cache] ──(Stream result via Tabular TDS endpoint ke Report Canvas)
```

#### B. Object-Level Security (OLS) Internal Mechanism
Berbeda dengan RLS yang memfilter baris data namun tetap membiarkan metadata tabel dan kolom terlihat (*schema exposure*), OLS memodifikasi visibilitas metadata pada level skema model tabular:
- Dikonfigurasi langsung pada metadata model (via XMLA Endpoint menggunakan TOM/TMSL).
- Jika sebuah kolom/tabel di-set `metadataPermission: none` untuk suatu Role, pengguna non-admin yang memicu kueri terhadap objek tersebut akan menerima *engine exception*: `Query (line, col) The column/table 'X' referenced in this query cannot be found or you do not have permission to view it.`
- Metadata kolom disembunyikan sepenuhnya dari skema visual, Intellisense, dan Discovery API engine. 

#### C. Arsitektur Jaringan: Managed VNet vs On-Premises Data Gateway
Akses data aman ke sumber data privat (misal: Azure Synapse, SQL Managed Instance, On-premises DB) diatur melalui dua pola:

```
[ Power BI Service (Fabric Cloud) ]
                │
         (Private Endpoint)
                ▼
[ Managed VNet Data Gateway ] ──(ExpressRoute / S2S VPN)──> [ Corporate On-Premises DB ]
                │
                └──(VNet Peering)──> [ Azure SQL DB / Databricks (Private Endpoint) ]
```

- **Managed VNet Gateway**: Power BI Service menginjeksi antarmuka jaringan langsung ke subnet VNet pelanggan di Azure. Eliminasi *single point of failure* (SPOF) dari On-Premises Data Gateway tradisional, mendukung *auto-scaling*, dan menghilangkan *management overhead* sistem operasi gateway (Windows Server patch management).
- **Kerberos Constrained Delegation (KCD)**: Pada skenario DirectQuery dengan Entra ID SSO, token pengguna diterjemahkan menjadi Service Ticket Active Directory on-premise menggunakan KCD protocol transition, mempertahankan *identity-flow* dari visual hingga database engine target.

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan (Why) | Apa Karakteristiknya (What) |
| :--- | :--- | :--- |
| **Dynamic Recursive RLS** | Struktur organisasi bisnis bersifat hierarkis (misal: Manajer regional membawahi beberapa Area Manager, yang membawahi Store Manager). Mengelola *role* statis per cabang menghasilkan ledakan matriks keamanan (*role combinatorial explosion*). | Pola DAX berbasis `PATH` dan `PATHCONTAINS` yang mengevaluasi relasi parent-child secara dinamis dalam satu tabel model tanpa fragmentasi *role*. |
| **Object-Level Security (OLS)** | Kepatuhan regulasi finansial (PCI-DSS) dan privasi data medis (HIPAA). Data sensitif seperti `Nomor Rekening Nasabah` atau `Gaji` tidak boleh diekspos meski pada baris yang diizinkan untuk diakses. | Menolak akses skema dan data secara total untuk kolom/tabel tertentu berdasarkan evaluasi Role, mencegah agregasi *unauthorized* secara mutlak. |
| **Azure Private Link Integration** | Mencegah kebocoran data internal ke internet terbuka dan mematuhi mandat perbankan/institusi pemerintah terkait konektivitas tanpa *public IP*. | Mengisolasi lalu lintas masuk (*inbound traffic*) ke Power BI Tenant dan lalu lintas keluar (*outbound queries*) ke data sources melalui *private endpoints* dengan IP privat RFC 1918. |
| **Sensitivity Labels (Purview)** | Kebijakan perlindungan data harus tetap melekat saat file diekspor ke format dokumen eksternal (Excel, PDF, PowerPoint). | Integrasi Microsoft Information Protection (MIP) yang menyematkan metadata enkripsi kriptografis Rights Management Services (RMS) pada file hasil ekspor. |

---

### 5. How (Workflow Detail)

Alur kerja implementasi arsitektur keamanan dan tata kelola terpadu:

```
+---------------------------------------------------------------------------------------+
| FASE 1: Enterprise Modeling (TMDL/Tabular Editor & Model Development)                 |
| 1. Bangun Skema Snowflake/Star dengan jembatan Dynamic Security Bridge.               |
| 2. Definisikan Logika DAX Flattened Hierarchy menggunakan PATH functions.             |
| 3. Terapkan konfigurasi Object-Level Security (OLS) via TMSL metadata script.        |
+---------------------------------------------------------------------------------------+
                                           │
                                           ▼
+---------------------------------------------------------------------------------------+
| FASE 2: Network Infrastructure Isolation (Infra Team)                                 |
| 1. Provisioning Azure Managed Virtual Network (VNet) Gateway.                        |
| 2. Konfigurasi Private Endpoints untuk Power BI Tenant (Inbound & Outbound).          |
| 3. Kunci Firewall Data Source (SQL Server, Data Lake) untuk blokir Public IP.         |
+---------------------------------------------------------------------------------------+
                                           │
                                           ▼
+---------------------------------------------------------------------------------------+
| FASE 3: Automated CI/CD & Governance Pipeline (DevOps/Platform Engineer)             |
| 1. Autentikasi Service Principal ke Fabric XMLA Endpoint via Client Secret/Cert.     |
| 2. Eksekusi Skrip PowerShell / Fabric CLI untuk validasi Role Assignment.            |
| 3. Deployment Artifacts (TMDL) ke Dev -> UAT -> Prod Workspace.                       |
+---------------------------------------------------------------------------------------+
                                           │
                                           ▼
+---------------------------------------------------------------------------------------+
| FASE 4: Audit & Real-time Monitoring (Security & Compliance Office)                   |
| 1. Ingestion Activity Logs via Power BI REST API / Purview Audit Log ke Log Analytics.|
| 2. Monitoring kebocoran ekspor via Defender for Cloud Apps.                           |
| 3. Sinkronisasi Sensitivity Labels & Kebijakan Data Loss Prevention (DLP).           |
+---------------------------------------------------------------------------------------+
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengamanan Kompleks Perbankan Multi-Gedung
- **Workspace Access**: Kartu akses gerbang utama kawasan perbankan (Hanya menentukan apakah Anda boleh masuk gedung Departemen Keuangan atau Departemen HRD).
- **Row-Level Security (RLS)**: Dokumen neraca keuangan yang hanya memperlihatkan baris pembukuan cabang wilayah Anda; baris cabang lain ditutupi tinta hitam permanen (*redacted*).
- **Object-Level Security (OLS)**: Dokumen memiliki amplop tertutup khusus berisi "Catatan Saldo Rahasia Direksi". Jika Anda staf biasa, Anda bahkan tidak diizinkan mengetahui bahwa amplop itu ada di dalam ruangan tersebut.
- **Private Link / VNet**: Terowongan bawah tanah anti-sadap berkeamanan militer yang menghubungkan brankas data pusat langsung ke ruang rapat analisa, tanpa pernah melewati trotoar jalan raya umum (Internet publik).

#### Diagram Resolusi Kueri RLS + OLS Terenkapsulasi

```
                  +----------------------------------------------+
                  |   Pengguna: budi@corp.com (Regional Manager) |
                  +----------------------------------------------+
                                         │
                                  Kueri Eksekusi
                                         │
                                         ▼
+──────────────────────────────────────────────────────────────────────────────────+
| Power BI Service: Analysis Services VertiPaq Engine                              |
|                                                                                  |
|  [ROLE ASSIGNMENT: Regional_Role]                                                |
|                                                                                  |
|  1. EVALUASI OLS (TMDL/TMSL):                                                    |
|     - Tabel 'FactPayroll': Permission = NONE                                     |
|     - Kolom 'DimCustomer'[SSN]: Permission = NONE                                |
|     => Engine menyembunyikan metadata kolom/tabel di atas dari Abstract Syntax   |
|        Tree (AST). Jika pengguna mereferensikan kolom SSN -> Query Error 403.    |
|                                                                                  |
|  2. EVALUASI RLS DINAMIS (DAX):                                                  |
|     Predicate: PATHCONTAINS(DimEmployee[HierarchyPath],                          |
|                  LOOKUPVALUE(DimEmployee[EmployeeKey],                           |
|                              DimEmployee[UserPrincipalName],                     |
|                              USERPRINCIPALNAME()))                               |
|                                                                                  |
|  3. VERTIFAQ STORAGE ENGINE PRUNING:                                             |
|     Data Partition: [Row 1 - Region West] -> TRUE  (Keep)                        |
|     Data Partition: [Row 2 - Region East] -> FALSE (Prune)                       |
|     Data Partition: [Row 3 - Region Central]-> FALSE (Prune)                     |
+──────────────────────────────────────────────────────────────────────────────────+
                                         │
                              Data Terfilter Terbatas
                                         │
                                         ▼
                     +────────────────────────────────────────+
                     | Visual Rendered: Hanya Wilayah West    |
                     | Kolom SSN & Payroll sama sekali lenyap |
                     +────────────────────────────────────────+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Basic Dynamic RLS
Implementasi pemetaan sederhana 1:1 antara tabel keamanan dan data target.

##### Definisi Filter DAX pada Tabel `DimSalesTerritory`:
```dax
[TerritoryManagerEmail] = USERPRINCIPALNAME()
```

---

#### B. Practical Example (Enterprise Standard)
Arsitektur pengamanan hierarki rekursif multi-level (Parent-Child) menggunakan flattened paths DAX, dipadukan dengan konfigurasi TMSL untuk mematikan akses ke tabel sensitif (OLS).

##### 1. Skrip M/Power Query: Pembuatan Kolom Hirarki Rekursif di ETL Layer
Untuk performa optimal, perhitungan jalur hierarki dihitung saat pemrosesan data (atau via calculated column di engine VertiPaq jika data berukuran menengah).

##### 2. Definisi DAX Calculated Column pada `DimEmployee`:
```dax
EmployeeHierarchyPath = 
PATH ( DimEmployee[EmployeeKey], DimEmployee[ParentEmployeeKey] )
```

##### 3. Definisi Dynamic RLS Filter pada Tabel `DimEmployee`:
Filter ini memastikan seorang atasan dapat melihat datanya sendiri dan semua data seluruh bawahan di bawah garis komandonya, sementara staf biasa hanya melihat datanya sendiri.

```dax
VAR CurrentUserEmail = USERPRINCIPALNAME()
VAR CurrentUserKey = 
    LOOKUPVALUE (
        DimEmployee[EmployeeKey],
        DimEmployee[EmailAddress], CurrentUserEmail
    )
RETURN
    IF (
        ISBLANK ( CurrentUserKey ),
        FALSE (), -- Blokir akses secara default jika identitas tidak terdaftar
        PATHCONTAINS ( DimEmployee[EmployeeHierarchyPath], CurrentUserKey )
    )
```

##### 4. Propagasi Filter ke Fact Table
Pastikan relasi antara `DimEmployee` dan `FactSales` bersifat **Single Direction** (1:Many). Filter kontekstual yang diterapkan oleh RLS pada `DimEmployee` akan secara otomatis merambat turun (*filter down*) ke `FactSales` melalui relasi `EmployeeKey`.

##### 5. Penerapan Object-Level Security (OLS) Menggunakan TMSL
Simpan skrip JSON berikut dan jalankan terhadap XMLA Endpoint model menggunakan Tabular Editor CLI, SQL Server Management Studio (SSMS), atau skrip otomatisasi:

```json
{
  "createOrReplace": {
    "object": {
      "database": "Sales_Intelligence_Enterprise",
      "role": "Role_Field_Sales_Representative"
    },
    "role": {
      "name": "Role_Field_Sales_Representative",
      "modelPermission": "read",
      "tablePermissions": [
        {
          "name": "FactExecutiveCompensation",
          "metadataPermission": "none"
        },
        {
          "name": "DimCustomer",
          "columnPermissions": [
            {
              "name": "TaxIdentificationNumber",
              "metadataPermission": "none"
            },
            {
              "name": "CreditScore",
              "metadataPermission": "none"
            }
          ]
        }
      ]
    }
  }
}
```

##### 6. Skrip Otomatisasi Administrasi: PowerShell + Power BI REST API
Otomatisasi pengikatan (assignment) Security Group Entra ID ke Role RLS/OLS model tabular pasca-deployment rilis produksi via Enterprise REST API:

```powershell
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true)]
    [string]$TenantId,
    [Parameter(Mandatory = $true)]
    [string]$ClientId,
    [Parameter(Mandatory = $true)]
    [string]$ClientSecret,
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceId,
    [Parameter(Mandatory = $true)]
    [string]$DatasetId,
    [Parameter(Mandatory = $true)]
    [string]$RoleName,
    [Parameter(Mandatory = $true)]
    [string]$SecurityGroupEmail
)

# 1. Akuisisi Token OAuth 2.0 via Microsoft Entra ID
$TokenEndpoint = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
$Body = @{
    client_id     = $ClientId
    scope         = "https://analysis.windows.net/powerbi/api/.default"
    client_secret = $ClientSecret
    grant_type    = "client_credentials"
}
$TokenResponse = Invoke-RestMethod -Uri $TokenEndpoint -Method Post -Body $Body
$AccessToken = $TokenResponse.access_token

# 2. Assign Entra ID Group ke Role Model Tabular via REST API
$AuthHeader = @{
    "Authorization" = "Bearer $AccessToken"
    "Content-Type"  = "application/json"
}

$AssignRoleEndpoint = "https://api.powerbi.com/v1.0/myorg/groups/$WorkspaceId/datasets/$DatasetId/Default.AssignWorkspaceUser"
$Payload = @{
    "identifier"         = $SecurityGroupEmail
    "groupUserAccessRight" = "Viewer"
    "principalType"      = "Group"
} | ConvertTo-Json

Write-Host "Mengaitkan Group: $SecurityGroupEmail ke Workspace Model..."
Invoke-RestMethod -Uri $AssignRoleEndpoint -Method Post -Headers $AuthHeader -Body $Payload
Write-Host "Selesai. Role metadata tersinkronisasi."
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Klien
Sebuah Bank Digital Nasional (FinTech) dengan 15 juta nasabah mengoperasikan Semantic Model terpusat di Power BI Fabric P1 Capacity. Model ini digunakan secara bersamaan oleh:
1. Agen Customer Service (CS)
2. Branch Managers di 300 kantor cabang
3. Tim Analis Risiko & Kredit Kantor Pusat
4. C-Level Executives

#### Permasalahan Skalabilitas & Regulasi
- **Regulasi Ketat (OJK/PDP)**: Agen CS dan Branch Manager tidak boleh melihat skor kredit internal nasabah (`DimCustomer[CreditRating]`), nomor rekening bank lain, dan tabel data agregasi margin bunga (`FactNetInterestMargin`).
- **Data Explosion RLS**: Pendekatan awal menggunakan 300 *roles* statis (satu per cabang) gagal total: pemeliharaan metadata tidak terkendali, dan kapasitas memory VertiPaq melonjak drastis karena *cache sizing* per-*role*.
- **Data Leakage Risk**: Analis eksternal yang diundang sebagai Entra B2B Guest berpotensi mengekspor raw data melalui fitur "Analyze in Excel".

#### Solusi Arsitektural yang Diterapkan
1. **Dynamic RLS Flattened Structure**: Menghapus 300 role statis, digantikan oleh 1 Dynamic Role (`Enterprise_Branch_Security`) yang memanfaatkan tabel jembatan `SecurityBridgeUserBranch` ter-relasi ke `DimBranch` dengan filter:
   ```dax
   VAR ActiveUser = USERPRINCIPALNAME()
   VAR AuthorizedBranches = 
       CALCULATETABLE(
           VALUES(SecurityBridgeUserBranch[BranchID]),
           SecurityBridgeUserBranch[UserEmail] = ActiveUser
       )
   RETURN
       DimBranch[BranchID] IN AuthorizedBranches
   ```
2. **OLS Enforcement**: Melalui CI/CD TMDL build step, tabel `FactNetInterestMargin` dan kolom `DimCustomer[CreditRating]` diamankan dengan OLS untuk role branch dan CS. Jika visual mencoba menampilkan matriks margin, CS hanya melihat *blank visual tile* tanpa kegagalan sistem global.
3. **MIP Sensitivity Labels Auto-Labeling**: Kebijakan Purview mewajibkan penandaan label `Confidential / Highly Restricted` ke Semantic Model. Saat user mengekspor data ke format `.xlsx`, Excel secara otomatis dienkripsi dengan proteksi RMS; hanya akun korporat berwenang yang dapat membuka file di komputer luar kantor.
4. **VNet Isolation**: Akses Semantic Model ke Azure Cosmos DB backend dikunci melalui Azure Private Endpoint. Gateway publik dinonaktifkan sepenuhnya.

---

### 9. Trade-offs

```
                  ┌──────────────────────────────────────────────┐
                  │          Import Mode + Dynamic RLS           │
                  │  - Performa Kueri Sub-detik (VertiPaq)       │
                  │  - Beban Memori Tinggi per Sesi Konkuren    │
                  └──────────────────────┬───────────────────────┘
                                         │
                             TRADE-OFF MATRIX ARSITEKTUR
                                         │
                  ┌──────────────────────┴───────────────────────┐
                  │         DirectQuery + Entra ID SSO           │
                  │  - Zero Data-at-Rest pada Power BI           │
                  │  - Latensi Database Source Membengkak         │
                  └──────────────────────────────────────────────┘
```

| Dimensi Arsitektur | Opsi A: Import Mode + Dynamic RLS | Opsi B: DirectQuery + Entra ID SSO / Pushdown |
| :--- | :--- | :--- |
| **Performance (Latensi)** | Sangat Cepat (Sub-detik). Pemrosesan agregasi dan evaluasi RLS terjadi di RAM VertiPaq. | Rentan lambat (High Latency). Setiap klik visual memicu pengiriman kueri SQL baru ke database target melalui Gateway. |
| **Scalability (Memori)** | Membutuhkan RAM berukuran besar di Kapasitas Fabric/P-SKU karena cache RLS disimpan terpisah per identitas pengguna aktif (*Cache Partitioning*). | Efisiensi memori tinggi di Power BI, namun memindahkan beban CPU/IOPS secara ekstrem ke server database sumber (Warehouse/Databricks). |
| **Karakteristik OLS** | Visual me-render pesan kesalahan visual terisolasi jika kolom diakses secara tidak sah; DAX Measure tidak boleh merujuk ke kolom OLS tanpa mekanisme *safe-fallback*. | Kerentanan *Failed Query Parsing* di tingkat database engine target jika translasi *SQL View* tidak sesuai. |
| **Biaya (Cost)** | Kapasitas Fabric/Power BI P-SKU harus lebih tinggi (misal: F64/P1 minimum) untuk menampung *cache overhead*. | Kapasitas Power BI lebih rendah (F8/F16 cukup), namun biaya komputasi database target (misal: Azure Synapse DWUs/Databricks DBUs) membengkak. |

---

### 10. Common Mistakes & Troubleshooting

#### A. Broken Visual Error Akibat OLS Exposure
* **Gejala**: Pengguna dalam role OLS mengalami error global pada visual dashboard: *"An error occurred while rendering the report. The column 'X' cannot be found"*.
* **Akar Masalah**: Sebuah DAX Measure publik merujuk langsung ke kolom yang diproteksi OLS tanpa pengecekan:
  ```dax
  // BAD PRACTICE - Merusak visual jika MarginPercent di-OLS
  SalesMargin = SUM(FactSales[MarginAmount]) / SUM(FactSales[Revenue])
  ```
* **Solusi**: Isolasi measure yang memanfaatkan kolom OLS ke dalam display folder terpisah, atau buat eksplisit measure berbasis *error-handling* atau batasi akses measure itu sendiri menggunakan OLS.

#### B. DirectQuery Kerberos Delegation Failures (Double-Hop Problem)
* **Gejala**: DirectQuery menghasilkan pesan: `Cannot connect to the SQL Server database. Login failed for user 'NT AUTHORITY\ANONYMOUS LOGON'`.
* **Akar Masalah**: Enterprise Data Gateway gagal melakukan delegasi token pengguna dari Service ke SQL Server lokal karena Kerberos SPN (*Service Principal Name*) belum didaftarkan di Domain Controller.
* **Solusi**:
  1. Daftarkan SPN untuk SQL Server service account:
     `setspn -S MSSQLSvc/dbserver.corp.local:1433 corp\sqlservice`
  2. Buka Active Directory Users and Computers -> Cari Machine/Service Account Gateway -> Tab *Delegation* -> Pilih *"Trust this computer for delegation to specified services only"* -> Pilih *"Use any authentication protocol"* (KCD Protocol Transition).

#### C. DAX Bi-Directional Cross-Filtering Security Leak
* **Gejala**: Pengguna melihat baris data yang seharusnya dilarang oleh RLS.
* **Akar Masalah**: Relasi *Both Directions* (Bi-directional) antara tabel dimensi dan tabel fakta lain membypass filter context RLS karena adanya ambiguasi jalur filter (*ambiguous relationship path*).
* **Solusi**: Selalu pertahankan relasi *Single Direction* untuk tabel sekuritas. Jika filter harus merambat ke dimensi lain, gunakan fungsi DAX `CROSSFILTER()` secara eksplisit di dalam measure yang terkontrol, bukan di arsitektur relasi model statis.

---

### 11. Best Practices (Production Checklist)

#### Security Architecture Checklist
- [ ] Nonaktifkan opsi tenant: *"Publish to Web"* secara total di tingkat Tenant Admin settings.
- [ ] Isolasi pengujian: Uji seluruh kombinasi Role menggunakan fitur *"View as Role"* di Power BI Desktop dan Power BI Service sebelum deployment produksi.
- [ ] Batasi hak ekspor data: Nonaktifkan izin *"Export to Excel with live connection"* bagi pengguna eksternal / guest users.
- [ ] Hapus semua hard-coded email address di dalam logika DAX; gantikan dengan dynamic identity mapping via Entra ID groups atau skema data terpisah.
- [ ] Pastikan seluruh Gateway memakai *TLS 1.2 minimum* dan cipher suite modern.

#### Governance & Auditability Checklist
- [ ] Deploy script otomatisasi untuk mengekstraksi *Power BI Activity Events Log* harian ke Azure Data Lake Storage (ADLS Gen2) via REST API `GetActivityEvents`.
- [ ] Tetapkan *Endorsement* status (`Certified` atau `Promoted`) hanya melalui verifikasi tim Center of Excellence (CoE).
- [ ] Gunakan Service Principal dengan akses *Read-Only Admin APIs* untuk keperluan monitoring Purview Catalog.

---

### 12. Hands-on Practice

Simpan seluruh file instruksi, skrip TMSL, dan DAX pada repositori proyek lokal di folder: `hands-on/m02/`.

#### Langkah 1: Persiapan Skema Data & Relasi
Buat Semantic Model dengan struktur tabel berikut:
1. `DimEmployee`: `EmployeeKey` (Int), `ParentEmployeeKey` (Int), `EmailAddress` (String).
2. `DimBranch`: `BranchID` (Int), `BranchName` (String).
3. `FactFinancials`: `TransactionID` (Int), `BranchID` (Int), `EmployeeKey` (Int), `Revenue` (Decimal), `NetProfit` (Decimal - SENSITIVE).

#### Langkah 2: Implementasi Dynamic Recursive RLS
Buka Power BI Desktop, masuk ke **Modeling** -> **Manage Roles** -> Buat role bernama `Hierarchical_Security`.
Masukkan DAX Expression pada tabel `DimEmployee`:

```dax
// File: hands-on/m02/dax/rls_hierarchy_filter.dax
VAR _LookupUserKey = 
    CALCULATE (
        MAX ( DimEmployee[EmployeeKey] ),
        FILTER (
            ALL ( DimEmployee[EmailAddress] ),
            DimEmployee[EmailAddress] = USERPRINCIPALNAME ()
        )
    )
RETURN
    IF (
        ISBLANK ( _LookupUserKey ),
        FALSE (),
        PATHCONTAINS (
            DimEmployee[EmployeeHierarchyPath],
            _LookupUserKey
        )
    )
```

#### Langkah 3: Eksekusi OLS via Tabular Editor (TMSL / CLI)
Buka Tabular Editor (versi 2/3) yang terhubung ke model.
1. Navigasikan ke Roles -> `Hierarchical_Security`.
2. Klik tabel `FactFinancials`. Ubah properti `TablePermission` menjadi `Read`.
3. Pilih kolom `NetProfit`. Pada panel properti, ubah `Object Level Security` -> pilih `None`.
4. Simpan model metadata ke database (`Ctrl + S` atau deploy via TMSL script).

Skrip TMSL yang dihasilkan (simpan di `hands-on/m02/tmsl/ols_rule.json`):
```json
{
  "createOrReplace": {
    "object": {
      "database": "TargetModelName",
      "role": "Hierarchical_Security"
    },
    "role": {
      "name": "Hierarchical_Security",
      "modelPermission": "read",
      "tablePermissions": [
        {
          "name": "FactFinancials",
          "columnPermissions": [
            {
              "name": "NetProfit",
              "metadataPermission": "none"
            }
          ]
        }
      ]
    }
  }
}
```

#### Langkah 4: Validasi Perilaku Engine
1. Di Desktop: Modeling -> **View as** -> Checklist `Hierarchical_Security` -> Masukkan user test email (misal: `manager_jakarta@corp.com`).
2. Buat Card Visual yang mereferensikan `NetProfit`. Verifikasi bahwa sistem melempar error: *"The field 'NetProfit' cannot be found or you are not authorized to view it."*
3. Buat Table Visual yang mereferensikan `DimEmployee[EmailAddress]`. Pastikan hanya branch/bawahan dari manager tersebut yang tampil pada canvas.

---

### 13. Exercise

#### Level Easy
Terapkan Dynamic RLS pada tabel `DimSalesTerritory` menggunakan kolom `CountryCode`.
- **Kriteria**: Pengguna hanya boleh melihat data negaranya sendiri sesuai token Entra ID yang cocok dengan `DimSecurityMapping[UserEmail]`.
- **Ekspresi DAX**: Gunakan `USERPRINCIPALNAME()` dan fungsi relasi `LOOKUPVALUE()` atau natural relationship filtering.

#### Level Medium
Sebuah perusahaan menggunakan matriks delegasi sementara (Cutover/Delegation Access). Manajer A dapat mendelegasikan otoritas melihat regionnya kepada Manajer B selama rentang tanggal tertentu (`StartDate` dan `EndDate`).
- **Kriteria**: Bangun tabel keamanan `DimDelegationSecurity` (`ManagerEmail`, `DelegateEmail`, `StartDate`, `EndDate`, `RegionID`).
- **Tugas**: Rancang ekspresi DAX RLS pada tabel `DimRegion` yang memvalidasi apakah pengakses adalah manajer definitif ATAU delegasi aktif berbasis `TODAY()`.

#### Level Hard
Sebuah organisasi memisahkan data anak perusahaan yang menggunakan skema multi-tenant dalam satu Semantic Model raksasa (500 juta baris).
- **Kriteria**: Gabungkan Recursive Hierarchy RLS (atasan-bawahan) DAN Multi-Tenant Tagging RLS (Tenant ID) sekaligus mematikan akses ke tabel `AuditLog` menggunakan OLS.
- **Tantangan Tambahan**: Optimalkan kueri DAX agar tidak menghasilkan *materialized intermediary table* yang melebihi kapasitas memori 1GB per query evaluation.

---

### 14. Challenge

#### Skenario Kasus Kompleks: Integrasi Merger & Akuisisi Pasca-Transisi
Perusahaan FinTech raksasa ("Corp-A") baru saja mengakuisisi kompetitor regional ("Corp-B"). Arsitektur sistem sedang dalam masa transisi:
1. Pengguna Corp-A memiliki UPN format `@corp-a.com`, sementara pengguna Corp-B masih menggunakan UPN format `@corp-b.net`.
2. Model analitik terpusat berada di Power BI Fabric Tenant Corp-A. Akun Corp-B diundang sebagai Entra B2B Guest users, sehingga identitas mereka terbaca sebagai `user_corp-b.net#EXT#@corp-a.onmicrosoft.com`.
3. Regulasi pasar modal mewajibkan batasan ketat: Eksekutif Corp-B hanya boleh melihat portofolio historis aset eks-Corp-B hingga proses merger disetujui regulator; sebaliknya, staf Corp-A dilarang melihat aset Corp-B tertentu.
4. **Tantangan Arsitektur**:
   - Rancang skema transformasi UPN normalisasi di level ETL/DAX untuk mendeteksi user internal vs guest external tanpa hardcoding domain.
   - Buat struktur dynamic role DAX yang mampu mengisolasi data cross-tenant secara deterministik.
   - Kolom evaluasi margin (`GrossAlphaRate`) harus diamankan via OLS sehingga bagi staf non-eksekutif, kueri yang menyentuh metrik ini dialihkan ke visual kustom atau *silent blank* tanpa melempar kegagalan sistem pada visual lain di laporan yang sama.
   - Dokumentasikan trade-off arsitektur jika solusi ini dibangun menggunakan Import Mode vs DirectQuery via Snowflake Cross-Tenant Sharing.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa fungsi internal DAX yang mengembalikan nama prinsipal pengguna dalam format `user@domain.com` pada Power BI Service?
2. Mengapa menerapkan Object-Level Security (OLS) tidak dapat dilakukan langsung secara native melalui graphical interface Power BI Desktop standar?
3. Apa perbedaan mendasar antara visibilitas data pada visual saat kolom dibatasi menggunakan Row-Level Security (RLS) vs dibatasi menggunakan Object-Level Security (OLS)?
4. Apa peran dari Service Principal dalam tata kelola keamanan dan deployment Power BI?
5. Apakah DirectQuery secara default mewarisi kredensial pengguna akhir (*end-user identity*) saat mengakses database sumber tanpa konfigurasi tambahan?

#### B. Pertanyaan Intermediate
6. Bagaimana VertiPaq Storage Engine menangani pemrosesan kueri ketika Dynamic RLS diaktifkan, dan mengapa hal tersebut berdampak pada konsumsi memori cache?
7. Mengapa penggunaan relasi dua arah (*bi-directional cross filtering*) sangat tidak direkomendasikan pada tabel yang terlibat dalam skema RLS?
8. Bagaimana protokol Kerberos Constrained Delegation (KCD) menyelesaikan masalah *Double-Hop authentication* pada On-Premises Data Gateway?
9. Apa yang terjadi pada file Excel hasil ekspor laporan Power BI jika Semantic Model induk memiliki Sensitivity Label bertipe `Highly Confidential - Encrypted`?
10. Bagaimana fungsi DAX `PATH()` dan `PATHCONTAINS()` mengeliminasi kebutuhan pembuatan puluhan *role security* statis pada struktur data organisasi hierarkis?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah visual laporan mendadak melempar error: `The syntax for 'FactRevenue' is incorrect or the table does not exist` khusus bagi pengguna role `RegionalSales`. Namun visual bekerja normal tanpa kendala untuk role `Executive`. Analis melaporkan bahwa tidak ada perubahan pada izin akses Workspace. Apa kemungkinan terbesar penyebab arsitektural dari error ini, dan bagaimana langkah mitigasinya?
12. **Skenario 2**: Kapasitas Fabric P1 perusahaan mengalami lonjakan memori (Over-consumption) drastis setiap jam 09.00 pagi saat 2.000 store managers membuka dashboard operasional cabang secara bersamaan. Semantic Model menggunakan Import Mode dengan Dynamic RLS. Analis menemukan formula RLS menggunakan fungsi iterator kompleks: `COUNTROWS(FILTER(...))`. Jelaskan mengapa formula tersebut memicu lonjakan memori dan bagaimana cara me-refactor formula tersebut agar VertiPaq dapat mengoptimalkan eksekusinya.
13. **Skenario 3**: Tim Keamanan Siber mewajibkan seluruh lalu lintas data dari Power BI Cloud ke Azure PostgreSQL Database terisolasi 100% dari jaringan internet publik. Namun konfigurasi *Managed VNet Gateway* gagal melakukan *handshake* koneksi. Sebutkan 3 titik kegagalan utama (*critical failure points*) pada konfigurasi jaringan Azure/Power BI yang harus diperiksa oleh Data Platform Engineer.

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Basic
1. `USERPRINCIPALNAME()`. (Fungsi `USERNAME()` di Power BI Service juga mengembalikan format UPN, namun di desktop mengembalikan domain\user).
2. Karena Power BI Desktop GUI dirancang untuk kemudahan pemodelan umum; manajemen skema metadata tingkat rendah seperti OLS memerlukan manipulasi TOM (Tabular Object Model) langsung yang diekspos melalui XMLA Endpoint menggunakan tools seperti Tabular Editor, ALM Toolkit, atau TMSL/TMDL.
3. RLS menyaring baris data namun skema (kolom/tabel) tetap ada dan dapat diagregasikan (menghasilkan nilai 0 atau Blank). OLS menyembunyikan skema secara total seolah kolom tersebut tidak pernah ada; jika kueri memanggil kolom ber-OLS, kueri akan gagal (*error exception*).
4. Service Principal bertindak sebagai identitas mesin (*headless/non-interactive identity*) berbasis Entra ID App Registration, menghilangkan ketergantungan pada akun pengguna individu untuk tugas otomatisasi CI/CD, rest-api scanning, dan administrasi deployment pipelines.
5. Tidak. Secara default DirectQuery menggunakan kredensial tunggal yang disimpan tetap (*fixed credentials*) saat koneksi dataset dibuat. Penerusan identitas pengguna akhir membutuhkan aktivasi explicit fitur SSO (DirectQuery via Entra ID SSO atau Kerberos).

#### Jawaban Intermediate
6. VertiPaq menginjeksi filter RLS ke dalam setiap sub-kueri. Hal ini memecah pembagian global cache (*global storage engine cache*): hasil kueri tidak dapat dibagi-pakai (*shared*) antar-pengguna dengan hak akses baris yang berbeda, sehingga engine harus mengalokasikan ruang memori terisolasi (*user-specific partition cache*) untuk setiap kombinasi profil keamanan pengguna yang aktif.
7. Relasi dua arah dapat membuka jalur propagasi filter alternatif yang tidak terduga (*filter hijacking* atau ambiguasi). Filter konteks dari tabel fakta yang tidak diamankan dapat merambat balik ke tabel dimensi lain, menerobos isolasi RLS dan mengekspos data yang seharusnya tersembunyi.
8. KCD mengizinkan On-Premises Data Gateway yang berjalan di bawah service account domain untuk menukarkan tiket autentikasi pengguna Entra ID (yang diterima via cloud) menjadi Windows Kerberos Ticket lokal untuk mengakses resource SQL Server di backend secara sah atas nama (*on behalf of*) pengguna tersebut.
9. Enkripsi RMS (Rights Management Services) yang tertanam pada Sensitivity Label secara otomatis diterapkan pada file `.xlsx` yang diunduh. File terenkripsi secara kriptografis; pengguna luar yang tidak memiliki hak dekripsi Entra ID tidak akan dapat membuka file tersebut meskipun berhasil mencuri file fisik dokumennya.
10. `PATH()` meratakan (*flattens*) pohon hierarki parent-child yang dinamis menjadi string terindeks (misal: `"|101|108|125|"`). `PATHCONTAINS()` kemudian melakukan pencarian berbasis bit-slice secara cepat pada string tersebut untuk menentukan apakah ID pengakses berada di dalam garis hierarki entitas tersebut, menggantikan logika pencarian rekursif yang berat dan memangkas jumlah role menjadi satu role dinamis global.

#### Panduan Jawaban Skenario Kasus Produksi
11. **Analisis Skenario 1**:
    - **Akar Masalah**: Kolom atau tabel `FactRevenue` telah dikonfigurasi dengan Object-Level Security (OLS) bernilai `metadataPermission: none` untuk role `RegionalSales`. Sebuah measure publik di dashboard kemungkinan mencoba membaca tabel tersebut, atau visual menyertakan kolom dari tabel itu secara langsung.
    - **Mitigasi**: Pastikan measure memiliki proteksi abstraksi (buat versi measure aman terpisah untuk konsumsi regional), atau sesuaikan permission role TMSL agar tabel `FactRevenue` memiliki permission minimum `read` dengan pembatasan berbasis RLS pada baris, bukan OLS total, jika laporan visual yang sama ditujukan untuk digunakan bersama oleh kedua role.
12. **Analisis Skenario 2**:
    - **Akar Masalah**: Fungsi iterator DAX seperti `FILTER()` dan `COUNTROWS()` di dalam predikat RLS memaksa engine berpindah dari Storage Engine (VertiPaq) ke Formula Engine (single-threaded). Ketika 2.000 manajer mengeksekusi ini secara konkuren, Formula Engine tidak mampu memparalelkan kalkulasi dan menahan *uncompressed temporary tables* dalam memori, memicu lonjakan memori dan latensi kueri yang ekstrem.
    - **Refactoring Solusi**: Hilangkan iterator DAX. Ubah logika menjadi operasi semi-join atau lookup berbasis relasi fisik bintang (*star schema*) menggunakan relasi single-direction dengan filter:
      ```dax
      // Optimized Pattern:
      DimBranch[BranchID] IN 
          CALCULATETABLE(
              VALUES(SecurityBridgeUserBranch[BranchID]),
              SecurityBridgeUserBranch[UserEmail] = USERPRINCIPALNAME()
          )
      ```
13. **Analisis Skenario 3**:
    Tiga titik kegagalan kritis yang harus diperiksa:
    - **Delegasi Subnet Azure**: Subnet yang dialokasikan untuk Managed VNet Gateway belum didelegasikan secara tepat ke namespace service `Microsoft.PowerPlatform/vnetaccesslinks`.
    - **Network Security Group (NSG) Outbound Rules**: Aturan NSG pada subnet Azure PostgreSQL memblokir *inbound traffic* dari subnet gateway atau Private Endpoint IP, atau port target (default 5432) terhalang oleh firewall internal.
    - **Integrasi Private DNS Zone**: VNet tidak memiliki tautan (*virtual network link*) ke Private DNS Zone Azure (`privatelink.postgres.database.azure.com`), sehingga Managed Gateway menyelesaikan FQDN PostgreSQL ke IP Publik yang ditolak oleh firewall, bukan ke alamat Private IP RFC 1918.

---

### 16. Summary

- **Enterprise Data Security** pada Power BI/Fabric menuntut pergeseran dari sekuritas berbasis visual statis ke sekuritas berbasis data engine terpadu menggunakan TMDL/TMSL untuk mendefinisikan RLS dan OLS.
- **Dynamic Recursive RLS** dengan pendekatan DAX flattened-path (`PATH` & `PATHCONTAINS`) menyelesaikan problem *role combinatorial explosion*, memastikan ribuan hierarki manajerial dikelola secara dinamis di satu basis data.
- **Object-Level Security (OLS)** bertindak sebagai mekanisme pertahanan kepatuhan tertinggi yang menghapus eksposur metadata sensitif secara total dari visual dan Semantic Model.
- **Isolasi Infrastruktur Jaringan** melalui Managed VNet Gateway, Private Endpoints, dan Kerberos Constrained Delegation menutup celah kebocoran data di level jaringan (*network transport layer*), memastikan zero-trust connectivity dari visual cloud hingga database on-premises.
- **Tata Kelola Holistik (Governance)** dicapai dengan mengintegrasikan deployment berbasis Service Principal (CI/CD), audit harian activity logs via REST API, dan penegakan *data-at-rest encryption* memanfaatkan Microsoft Purview Information Protection Sensitivity Labels.