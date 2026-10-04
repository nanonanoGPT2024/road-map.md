# Kurikulum Enterprise: Power BI BI-DevOps, ALM, dan Automated Deployment Pipelines
**Kategori:** 08-AI-Data-and-Autonomous-Agents  
**Topik:** Power BI  
**Bab 09:** BAB-09-BI-DevOps-ALM-Automated-Deployment-Pipelines  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi  

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, data engineer dan BI platform engineer diharapkan mampu:
- Mengimplementasikan arsitektur *Application Lifecycle Management* (ALM) berbasis *Power BI Project* (PBIP) dan *Tabular Model Definition Language* (TMDL).
- Merancang dan mengeksekusi pipeline CI/CD otomatis menggunakan Azure DevOps / GitHub Actions yang terintegrasi langsung dengan Microsoft Fabric / Power BI Service melalui XMLA Read/Write Endpoint.
- Membangun gerbang validasi otomatis (*automated gating*) menggunakan Tabular Editor CLI dan Best Practice Analyzer (BPA) untuk menegakkan standar performa model DAX, partisi, dan penamaan objek.
- Menerapkan arsitektur *Zero-Downtime Deployment* pada Semantic Model skala enterprise menggunakan teknik *Blue/Green Partition Swapping* dan *Automated Metadata Deployment* tanpa memicu *full data refresh*.
- Menjalankan *automated regression testing* untuk DAX query dan integritas relasi semantic model sebelum artifak dipromosikan ke tahap *Production*.

---

## 2. Prerequisite
Untuk mengikuti modul ini dengan optimal, praktisi harus memiliki:
- **Kapasitas Power BI**: Power BI Premium Per Capacity (P-SKU) atau Fabric Capacity (F-SKU) dengan opsi XMLA Read/Write diaktifkan di tingkat Tenant Admin.
- **Service Principal**: Akun Azure AD / Entra ID Service Principal yang telah diberi izin akses REST API Power BI dan terdaftar di security group tenant Power BI.
- **Tooling Lokal**:
  - Power BI Desktop (rilis terbaru dengan opsi pratinjau PBIP aktif).
  - VS Code dengan ekstensi TMDL dan DAX.
  - Tabular Editor 2 (CLI) atau Tabular Editor 3 (CLI Enterprise).
  - PowerShell 7.x terinstal dengan modul `Az` dan `Microsoft.AnalysisServices.Tabular`.
- **Version Control System**: Akun Azure DevOps (Pipelines & Repos) atau GitHub (Actions & Repositories).

---

## 3. Concept & Internal Architecture (Mendalam)

Implementasi enterprise BI modern menuntut pergeseran paradigma dari *file-based monolithic artifacts* (ekstensi `.pbix`) menuju *declarative, code-first artifacts* (ekstensi `.pbip`).

```
                    STRUKTUR INTERNAL ARTIFAK PBIP
                    
[NamaProject].pbip (Pointer File)
  │
  ├── [NamaProject].Report/
  │     ├── definition.pbir             <-- Metadata integrasi semantic model
  │     ├── report.json                 <-- Konfigurasi visual, layout, bookmark
  │     └── .platform                   <-- Metadata internal Fabric Platform
  │
  └── [NamaProject].SemanticModel/
        ├── definition.pbism            <-- Definisi tipe semantic model
        ├── model.bim / definition/     <-- TMDL / TMSL schema
        │     ├── tables/               <-- Berisi file individual .tmdl per tabel
        │     ├── relationships.tmdl    <-- Definisi seluruh edge relasi
        │     ├── cultures.tmdl         <-- Konfigurasi lokalisasi
        │     └── database.tmdl         <-- Kompatibilitas engine & metadata DB
        └── .platform                   <-- Sinkronisasi state Fabric
```

### 3.1 TMDL (Tabular Model Definition Language) Engine
TMDL menggantikan struktur format tunggal JSON (`model.bim`) yang rentan terhadap *merge conflicts*. TMDL menggunakan sintaks minimalis terindentasi menyerupai YAML/Python yang memecah satu semantic model ke dalam folder dan file representatif untuk setiap tabel, kalkulasi kolom, hierarki, dan *measure*. 

Ketika developer mengubah satu measure dalam Power BI Desktop atau VS Code, sistem Git hanya mencatat *diff* baris kode pada file `.tmdl` tabel yang bersangkutan. Hal ini memungkinkan kolaborasi multi-developer secara konkuren tanpa risiko timpa-menimpa metadata.

### 3.2 Workspace Git Integration Synchronization Loop
Microsoft Fabric mengimplementasikan *Git Integration Engine* native yang secara periodik atau terpicu webhook mencocokkan status *head commit* di repositori remote (misalnya cabang `main`) dengan metadata yang tersimpan di Analysis Services VertiPaq engine di Power BI Service.

```
       ARUS SINKRONISASI FABRIC GIT INTEGRATION & XMLA
       
 +------------------+           Git Push           +---------------------+
 | Developer Local  | ---------------------------> | Remote Git Repo     |
 | (PBIP / TMDL)    |                              | (ADO / GitHub)      |
 +------------------+                              +---------------------+
                                                              │
                                                        Webhook Event /
                                                        REST API Call
                                                              │
                                                              ▼
 +-----------------------------------------------------------------------+
 |                     Microsoft Fabric Workspace                        |
 |                                                                       |
 |   +----------------------+                     +------------------+   |
 |   | Fabric Git Sync Core | <---(Workspace API)-| Git Status Check |   |
 |   +----------------------+                     +------------------+   |
 |              │ (Commit/Update)                                        |
 |              ▼                                                        |
 |   +---------------------------------------------------------------+   |
 |   | Analysis Services Instance (SSAS / VertiPaq Engine)           |   |
 |   |  - Metadata Sync (TMSL/TOM Scripting via XMLA Port)           |   |
 |   |  - Partition Maintenance (Direct Lake / Import / DirectQuery) |   |
 |   +---------------------------------------------------------------+   |
 +-----------------------------------------------------------------------+
```

### 3.3 TOM (Tabular Object Model) & XMLA Endpoint
Secara arsitektural, Semantic Model Power BI Premium di-host pada instans Analysis Services terisolasi. Port XMLA memungkinkan modifikasi objek model secara terprogram melalui TOM (Tabular Object Model) API. 

Dalam automated deployment enterprise, metadata deployment dapat dilakukan via XMLA menggunakan skrip PowerShell yang meng-instansiasi assembly `Microsoft.AnalysisServices.Tabular.Server`. Pendekatan ini memungkinkan:
- Pembaruan skema tabel, measure, dan metadata tanpa membuang partisi data yang sudah diproses (*Metadata-only deployment*).
- Pemisahan deployment skema dari runtime *refresh* data historis (menghemat waktu CI/CD dari hitungan jam menjadi hitungan detik).
- Penerapan manipulasi partisi data, incremental refresh policy, dan dynamic parameter injection tanpa intervensi antarmuka GUI.

---

## 4. Why & What

### Mengapa Pendekatan Tradisional (.pbix) Gagal di Skala Enterprise?
1. **Binary Blob Conflict**: Format biner `.pbix` tidak dapat digabung (*merge*) menggunakan algoritma diff Git bawaan. Dua developer yang mengerjakan measure berbeda pada file `.pbix` yang sama akan menghasilkan *unresolvable binary conflict*.
2. **Ketergantungan Deployment Penuh**: Setiap kali perubahan visual kecil dilakukan, seluruh file `.pbix` harus di-upload ulang. Hal ini dapat menghapus cache VertiPaq dan memaksa pemrosesan data ulang (*full processing*) yang membebani kapasitas komputasi (Capacity Units/CU).
3. **Ketiadaan Guardrails / Automated Testing**: Model analitik sering dirilis ke tahap produksi tanpa verifikasi sintaksis, pengujian regresi beban DAX, atau audit kepatuhan performa seperti penggunaan fungsi berbiaya komputasi tinggi (misal: `COUNTROWS(FILTER(...))` yang tidak efisien).

### Apa itu Modern Power BI DevOps?
Modern Power BI DevOps adalah penerapan rekayasa perangkat lunak modern pada siklus hidup intelijen bisnis:
- **Source Code Declarative**: Semua artifak dimodelkan dalam teks (TMDL untuk model, JSON untuk laporan).
- **Continuous Integration (CI)**: Setiap *Pull Request* memicu validasi otomatis: linting sintaks DAX, eksekusi Best Practice Analyzer via Tabular Editor CLI, dan deteksi duplikasi relasi.
- **Continuous Delivery (CD)**: Otomasi deployment dari dev -> UAT -> prod dengan penggantian parameter dinamis (connection string, database target, workspace ID) via pipeline script tanpa menyentuh file sumber.

---

## 5. How (Workflow Detail)

Alur kerja enterprise end-to-end terdiri dari 6 tahap berurutan:

```
               END-TO-END ENTERPRISE ALM WORKFLOW
               
 +--------------------+       +---------------------+       +---------------------+
 | [1] Local Dev      | ----> | [2] Pull Request    | ----> | [3] CI Validation   |
 | - VS Code / PBI    |       | - Target: 'develop' |       | - Syntax TMDL Check |
 | - TMDL + PBIP      |       | - Automated Trigger |       | - TE3 CLI BPA Rules |
 +--------------------+       +---------------------+       +---------------------+
                                                                       │
                                      +--------------------------------+
                                      │ (Pass)
                                      ▼
 +--------------------+       +---------------------+       +---------------------+
 | [6] Production     | <---- | [5] Staging / UAT   | <---- | [4] CD Deployment   |
 | - Pipeline Promo   | (Appr)| - Automated DAX Test|       | - Push to Dev WS    |
 | - Blue/Green Swap  |       | - Direct Lake Sync  |       | - Parameter Swap    |
 +--------------------+       +---------------------+       +---------------------+
```

### Rincian Tahapan Implementasi:
1. **Local Development**: Developer membuat branch fitur (`feat/measure-customer-churn`). Modifikasi dilakukan di Power BI Desktop (disimpan dalam format `.pbip`) atau langsung mengedit file TMDL via VS Code.
2. **Code Review & Static Analysis**: Developer membuka PR ke branch `develop`. Pipeline CI berjalan secara *headless*, mengekstrak file model, dan menjalankan Tabular Editor CLI untuk memeriksa *Best Practice Analyzer* (BPA). PR diblokir jika terdapat aturan level `Error` yang dilanggar.
3. **Artifact Build & Packaging**: Skrip pipeline mengompilasi TMDL menjadi database TMSL (Tabular Model Scripting Language) tunggal.
4. **Development Workspace Deployment**: CD pipeline mengalirkan skema metadata ke Dev Workspace menggunakan REST API Fabric Git Sync atau skrip PowerShell XMLA via Service Principal.
5. **Regression Testing & Validation**: Test runner berbasis skrip mengeksekusi kumpulan query DAX penting terhadap endpoint dev/staging dan memverifikasi waktu respons serta integritas baris data.
6. **Production Promotion**: Perubahan dipromosikan ke tahap *Production* melalui Fabric Deployment Pipelines atau eksekusi *Zero-Downtime Swap* melalui XMLA.

---

## 6. Analogy & Diagram ASCII

### Analogi Konstruksi Bangunan
Mengelola BI dengan file `.pbix` tradisional ibarat memindahkan **rumah yang sudah jadi secara utuh (modular pod biner)** setiap kali ingin mengganti warna cat tembok di kamar mandi. Jika fondasi bergeser sedikit, seluruh rumah harus dibongkar ulang.

Sebaliknya, **Modern PBIP + TMDL ALM** ibarat bekerja dengan **cetak biru arsitektur berbasis teks (CAD scripts)**. Jika ingin mengganti warna cat kamar mandi, Anda cukup mengirim dokumen revisi 1 lembar (sebuah file `.tmdl`). Tim konstruksi (CI/CD Pipeline) membaca lembar tersebut, mendatangi ruangan spesifik, dan mengecat ulang bidang yang dimaksud tanpa membongkar fondasi bangunan (data cache VertiPaq tetap utuh).

### Arsitektur Sistem Produksi

```
                         ARSITEKTUR DEVOPS PRODUKSI
                         
 +--------------------------------------------------------------------------+
 |                            AZURE REPOSITORIES                            |
 |                                                                          |
 |  feature/*  ─────────► develop ──────────────► release/* ────────► main  |
 +---------------------------│------------------------│-----------------│---+
                             │                        │                 │
                   Azure DevOps CI Build    Azure DevOps CD Deploy      │
                             │                        │                 │
                             ▼                        ▼                 │
               +---------------------------+   +-------------------+    │
               | Runner / Pipeline Agent   |   | Service Principal |    │
               |  - Tabular Editor 3 CLI   |   | Authentication    |    │
               |  - Run BPA Audit Rules    |   +-------------------+    │
               |  - Execute DAX Unit Tests |              │             │
               +---------------------------+              ▼             │
                                              +---------------------+   │
                                              | Power BI / Fabric   |   │
                                              | REST API & XMLA     |   │
                                              +---------------------+   │
                                                          │             │
                                                          ▼             ▼
 +--------------------------------------------------------------------------+
 |                         MICROSOFT FABRIC TENANT                          |
 |                                                                          |
 |  +--------------------+   +--------------------+   +-------------------+ |
 |  | Workspace: [DEV]   |   | Workspace: [UAT]   |   | Workspace: [PROD] | |
 |  | Direct Sync Repos  |──►| Deployment Pipeline|──►| Deployment Pipeline|
 |  | (Dev Git Branch)   |   | (Release Branch)   |   | (Production Tag)  | |
 |  +--------------------+   +--------------------+   +-------------------+ |
 +--------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: TMDL vs Legacy Format

Berikut adalah representasi file `CustomerChurn.tmdl` individual dalam struktur PBIP modern:

```tmdl
table 'Customer Sales'
	lineageTag: 7a82c421-399a-4c21-9e12-82cb82fa8101

	measure 'Total Revenue' = SUM('Customer Sales'[SalesAmount])
		formatString: \$#,0.00
		lineageTag: 9b2d8819-0129-4d62-9e88-34ab89cb0123

	measure 'Revenue YoY Growth %' = 
			VAR CurrentYearSales = [Total Revenue]
			VAR PreviousYearSales = CALCULATE([Total Revenue], SAMEPERIODLASTYEAR('Date'[Date]))
			RETURN
				DIVIDE(CurrentYearSales - PreviousYearSales, PreviousYearSales, 0)
		formatString: 0.00%
		lineageTag: 4f1a2311-8201-44ab-bb21-12ec89123456

	column CustomerKey
		dataType: int64
		sourceColumn: CustomerKey
		summarizeBy: none
		isKey

	column SalesAmount
		dataType: decimal
		sourceColumn: SalesAmount
		summarizeBy: sum

	partition 'Customer Sales-AutoPartition' = m
		mode: import
		source = 
			let
				Source = Sql.Database(#"ServerName", #"DatabaseName"),
				dbo_FactSales = Source{[Schema="dbo",Item="FactSales"]}[Data]
			in
				dbo_FactSales
```

### 7.2 Practical Example: Azure DevOps CI/CD YAML Pipeline
Pipeline produksi berikut menerapkan pengujian Best Practice Analyzer (BPA) secara headless, serialisasi TMDL, dan deployment metadata ke Analysis Services/Fabric Workspace melalui XMLA endpoint dengan autentikasi Service Principal.

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include:
      - main
      - develop

variables:
  - group: PowerBI-ALM-Variables # Berisi PBI_TENANT_ID, PBI_CLIENT_ID, PBI_CLIENT_SECRET
  - name: WorkspaceDevConnection
    value: "powerbi://api.powerbi.com/v1.0/myorg/Contoso-BI-Dev"
  - name: SemanticModelName
    value: "EnterpriseSalesAnalytics"

pool:
  vmImage: 'windows-latest'

stages:
- stage: Validate
  displayName: "Continuous Integration & Quality Gate"
  jobs:
  - job: AnalyzeModel
    displayName: "TMDL Static Analysis & BPA Check"
    steps:
    - task: PowerShell@2
      displayName: "Install Tabular Editor 3 & Run BPA"
      inputs:
        targetType: 'inline'
        script: |
          Write-Host "Mengunduh Tabular Editor Portable CLI..."
          Invoke-WebRequest -Uri "https://github.com/TabularEditor/TabularEditor/releases/download/2.24.2/TabularEditor.Portable.zip" -OutFile "TE.zip"
          Expand-Archive -Path "TE.zip" -DestinationPath "$(Agent.TempDirectory)\TE"

          $modelPath = "$(Build.SourcesDirectory)/src/EnterpriseSalesAnalytics.SemanticModel"
          $bpaRulesPath = "$(Build.SourcesDirectory)/ci/bpa-rules.json"

          Write-Host "Mengeksekusi Best Practice Analyzer pada model..."
          $tePath = "$(Agent.TempDirectory)\TE\TabularEditor.exe"
          
          # Eksekusi BPA. Jika ada error kepatuhan kritis, return exit code 1
          & $tePath $modelPath -A $bpaRulesPath -V
          if ($LASTEXITCODE -ne 0) {
            Write-Error "Validasi Best Practice Analyzer gagal! Tinjau aturan pemodelan dan DAX Anda."
            exit 1
          }
          Write-Host "Validasi BPA Berhasil tanpa pelanggaran kritis."

- stage: DeployDev
  displayName: "Continuous Deployment to DEV"
  dependsOn: Validate
  condition: succeeded()
  jobs:
  - job: DeployMetadata
    displayName: "XMLA Metadata Synchronization"
    steps:
    - task: PowerShell@2
      displayName: "Execute TOM Deployment Script"
      env:
        TENANT_ID: $(PBI_TENANT_ID)
        CLIENT_ID: $(PBI_CLIENT_ID)
        CLIENT_SECRET: $(PBI_CLIENT_SECRET)
      inputs:
        targetType: 'inline'
        script: |
          # Import Microsoft Analysis Services TOM Engine
          Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force
          Install-Module -Name Microsoft.AnalysisServices.Tabular -Scope CurrentUser -Force
          Import-Module Microsoft.AnalysisServices.Tabular

          $tenantId = $env:TENANT_ID
          $clientId = $env:CLIENT_ID
          $secret = $env:CLIENT_SECRET
          $workspaceUrl = "$(WorkspaceDevConnection)"
          $dbName = "$(SemanticModelName)"
          $sourcePath = "$(Build.SourcesDirectory)/src/EnterpriseSalesAnalytics.SemanticModel"

          $connStr = "Provider=MSOLAP;Data Source=$workspaceUrl;User ID=app:$clientId@$tenantId;Password=$secret;Persist Security Info=True;Impersonation Level=Impersonate;"

          Write-Host "Membuka koneksi XMLA ke: $workspaceUrl"
          $server = New-Object Microsoft.AnalysisServices.Tabular.Server
          $server.Connect($connStr)

          Write-Host "Membaca definisi TMDL lokal..."
          $localDatabase = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder($sourcePath)

          if ($server.Databases.ContainsName($dbName)) {
              Write-Host "Database $dbName ditemukan. Memperbarui Metadata (Incremental Metadata Sync)..."
              $targetDb = $server.Databases[$dbName]
              
              # Sinkronisasi model tanpa menghapus partisi data eksisting
              $localDatabase.Model.CopyTo($targetDb.Model)
              $targetDb.Model.SaveChanges()
              Write-Host "Metadata model berhasil diperbarui secara in-place."
          } else {
              Write-Host "Database $dbName belum ada. Melakukan create database baru..."
              $localDatabase.Name = $dbName
              $server.Databases.Add($localDatabase)
              $localDatabase.Update()
              Write-Host "Database berhasil dibuat di Fabric Workspace."
          }

          $server.Disconnect()
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Global FinTech Platform (PT Finansial Nusaprima Inti)
- **Kondisi Awal**: 
  - Mengelola 1 Enterprise Semantic Model inti sebesar 140 GB VertiPaq compressed di Fabric F128 Capacity.
  - 18 BI Developer melakukan edit pada file biner `.pbix` sebesar 2.1 GB yang disimpan di SharePoint.
  - Setiap deployment ke produksi membutuhkan waktu **4,5 jam** karena deployment `.pbix` memicu *full re-process* pada tabel transaksi buku besar (*General Ledger*) yang berisi 1,8 miliar baris.
  - Sering terjadi *out-of-memory* (OOM) capacity error dan *silent data discrepancies* akibat merge file secara manual.

### Solusi Arsitektur ALM Terpadu:
1. **Dekomposisi ke PBIP & TMDL**: 
   Model biner dipecah ke format PBIP. Repositori di-host di Azure DevOps Repos. Setiap tabel dipisah menjadi file TMDL modular.
2. **Implementasi Metadata-Only Deployment**:
   Deployment beralih ke XMLA/TOM script via Azure Pipelines. Alih-alih meng-upload data bersama file biner, CI/CD pipeline hanya menyuntikkan delta definisi metadata (perubahan DAX, kalkulasi kolom baru).
3. **Partition-Aware Refresh Architecture**:
   Pipeline CD mengeksekusi skrip REST API untuk memproses data hanya pada partisi transaksi bulan berjalan (`Partition-2026-03`). Partisi historis (2015–2025) ditandai *read-only* dan tidak disentuh saat deployment.

### Dampak Metrik Produksi:
- **Waktu Deployment**: Berkurang dari **270 menit** menjadi **38 detik** (*metadata-only deploy*).
- **Merge Conflicts**: Berkurang 94%; sisa konflik pada file teks TMDL diselesaikan melalui antarmuka PR bawaan Git dalam hitungan menit.
- **Downtime Semantic Model**: 0 detik (tidak ada lagi *cache eviction* masif pada data historis).
- **Frekuensi Deployment**: Meningkat dari 1 kali per minggu menjadi rata-rata 6 kali per hari tanpa gangguan sistem.

---

## 9. Trade-offs

| Dimensi Arsitektur | Fabric Git Integration Native | Custom XMLA / TOM Script Pipelines | Fabric Deployment Pipelines (GUI) |
| :--- | :--- | :--- | :--- |
| **Kontrol Skrip & Fleksibilitas** | Terbatas pada git provider yang didukung & mapping workspace statis. | **Tinggi**: Kemampuan memodifikasi partisi, parameter, dan dynamic metadata. | Rendah: Mengandalkan antarmuka Fabric Web GUI standar. |
| **Kompatibilitas Format** | PBIP / TMDL native terintegrasi ke Workspace. | TMDL, TMSL, dan model berbasis file database C#. | Mendukung format internal Fabric secara langsung. |
| **Latensi Eksekusi Deployment** | Menengah (terikat engine sinkronisasi Fabric). | **Sangat Cepat** (langsung memanipulasi metadata via XMLA connection). | Menengah (proses duplikasi workspace backend memakan waktu). |
| **Kemampuan Automated Testing** | Rendah (hanya commit sync). | **Tinggi**: Dapat menyisipkan unit testing DAX sebelum dan sesudah deployment. | Rendah: Tidak ada backward gating script native. |
| **Biaya Operasional & Keahlian** | Rendah: Cukup konfigurasi GUI workspace. | Tinggi: Butuh keahlian scripting Analysis Services TOM, C#, atau PowerShell. | Rendah: User-friendly bagi business analyst non-teknis. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Merge Conflicts pada `diagramLayout.json`
- **Gejala**: Developer mengalami merge conflict pada file tersembunyi `diagramLayout.json` di dalam folder `.Report` atau `.SemanticModel`, padahal visual dan tabel yang diubah berbeda.
- **Penyebab**: Power BI Desktop secara otomatis memperbarui koordinat posisi visual/tabel (X, Y) setiap kali kanvas dibuka atau di-zoom.
- **Solusi**: Tambahkan baris berikut ke `.gitignore` proyek Anda:
  ```gitignore
  **/diagramLayout.json
  **/.pbi/localSettings.json
  ```
  Biarkan engine Power BI menyusun tata letak kanvas secara komparatif tanpa memantau setiap pergeseran pixel di level git versioning.

### 10.2 XMLA Deployment Merusak Kredensial Data Source
- **Gejala**: Setelah metadata dideploy via XMLA endpoint, semantic model menghasilkan error `The credentials provided for the DataSource are invalid` saat di-refresh.
- **Penyebab**: XMLA endpoint Analysis Services **secara desain tidak menerima kredensial sensitif** (password, service account secret) di dalam skrip TMSL/TMDL demi keamanan.
- **Solusi**: Pasang langkah otomatis pasca-deploy (*post-deploy step*) menggunakan Power BI REST API (`POST https://api.powerbi.com/v1.0/myorg/gateways/{gatewayId}/datasources/{datasourceId}`) atau cmdlet `Set-PowerBIDatasource` untuk mengatur ulang kredensial koneksi secara aman dari Key Vault.

### 10.3 Pelanggaran Hak Akses Tenant XMLA oleh Service Principal
- **Gejala**: Pipeline gagal dengan exception: `Microsoft.AnalysisServices.OperationException: The remote server returned an error: (401) Unauthorized / (403) Forbidden.`
- **Troubleshooting Checklist**:
  1. Pastikan Service Principal terdaftar di Microsoft Entra Security Group.
  2. Buka **Power BI Admin Portal** -> **Tenant Settings**.
  3. Pastikan **Allow service principals to use Power BI APIs** bernilai *Enabled* untuk Security Group tersebut.
  4. Pastikan **XMLA Endpoint: Allow read-write** diaktifkan untuk kapasitas target.
  5. Pastikan Service Principal memiliki role **Admin** atau **Member** (bukan Viewer) di Fabric Workspace target.

---

## 11. Best Practices (Production Checklist)

Gunakan checklist berikut sebelum mengalirkan artifak ke tahap produksi:

- [ ] **Struktur Repositori**: Repositori menggunakan format PBIP dengan konfigurasi serialisasi TMDL aktif (bukan file tunggal `model.bim`).
- [ ] **Audit Aturan Keamanan**: Tidak ada hardcoded credentials, IP addresses, atau personal tokens di dalam file `.tmdl` atau `.pbir` (gunakan parameter M terpusat).
- [ ] **Git Hook & Ignore**: File `.gitignore` mengabaikan cache lokal, file backup biner (`*.pbit`, `*.pbix`), serta file layout non-kritis.
- [ ] **Enforce Tabular Best Practice Analyzer (BPA)**:
  - Severity 1 (Error): Memblokir build pipeline jika ada measure yang error, relationship yang ambigu, atau kolom foreign key yang memiliki summary statistics aktif.
  - Severity 2 (Warning): Mengharuskan optimasi pada format string yang hilang atau tipe data *Floating Point* alih-alih *Fixed Decimal Currency*.
- [ ] **Partisi & Incremental Refresh**: Skema model mempertahankan partisi historis; deployment tidak memicu processing pada partisi *cold storage*.
- [ ] **Idempotent Deployment**: Skrip deployment bersifat *re-entrant* (aman dieksekusi berkali-kali tanpa menghasilkan duplikasi objek atau error *object already exists*).
- [ ] **Audit Trail**: Setiap deployment ke tahap Staging dan Production terikat dengan metadata `Commit SHA`, `Build ID`, dan identitas Service Principal di dalam log telemetry.

---

## 12. Hands-on Practice

Dalam praktikum ini, Anda akan membangun sistem validasi CI lokal menggunakan Tabular Editor CLI dan mengeksekusi simulasi deployment via PowerShell script.

### Struktur Folder Praktikum
Simpan seluruh artifak berikut di path: `hands-on/m02/`

```
hands-on/m02/
├── .gitignore
├── ci/
│   ├── bpa-rules.json
│   └── run-ci-validation.ps1
├── src/
│   └── SalesAnalytics.SemanticModel/
│       ├── definition.pbism
│       └── definition/
│           ├── database.tmdl
│           ├── model.tmdl
│           └── tables/
│               ├── Date.tmdl
│               └── FactSales.tmdl
└── deploy/
    └── deploy-model.ps1
```

### Langkah 1: Inisialisasi File Model (TMDL)

Buat file `hands-on/m02/src/SalesAnalytics.SemanticModel/definition/model.tmdl`:
```tmdl
model Model
	culture: en-US
	defaultPowerBIDataSourceVersion: powerBI_V3
	sourceQueryCulture: en-US
	dataAccessOptions
		legacyRedirects
		returnErrorValuesAsNull

annotation PBI_QueryOrder = ["FactSales","Date"]
```

Buat file `hands-on/m02/src/SalesAnalytics.SemanticModel/definition/tables/FactSales.tmdl`:
```tmdl
table FactSales
	lineageTag: a1b2c3d4-0001-0000-0000-000000000001

	measure 'Gross Sales' = SUM(FactSales[Amount])
		formatString: \$#,0.00
		lineageTag: a1b2c3d4-0002-0000-0000-000000000002

	measure 'Total Transactions' = COUNTROWS(FactSales)
		formatString: #,0
		lineageTag: a1b2c3d4-0003-0000-0000-000000000003

	column OrderID
		dataType: int64
		sourceColumn: OrderID
		summarizeBy: none

	column Amount
		dataType: decimal
		sourceColumn: Amount
		summarizeBy: sum

	partition FactSales-2026 = m
		mode: import
		source = 
			let
				Source = Table.FromRecords({
					[OrderID = 101, Amount = 1500.50],
					[OrderID = 102, Amount = 320.00]
				})
			in
				Source
```

### Langkah 2: Buat Aturan BPA (Best Practice Analyzer)

Buat file `hands-on/m02/ci/bpa-rules.json`:
```json
[
  {
    "ID": "DAX_NO_UNFORMATTED_MEASURES",
    "Name": "Measures must have a format string",
    "Category": "Formatting",
    "Severity": 1,
    "Scope": "Measure",
    "Expression": "string.IsNullOrEmpty(FormatString)"
  },
  {
    "ID": "PERF_AVOID_NUMERIC_SUMMARIZE",
    "Name": "Key columns should not be summarized",
    "Category": "Performance",
    "Severity": 2,
    "Scope": "DataColumn",
    "Expression": "Name.EndsWith(\"ID\") and SummarizeBy <> AggregateFunction.None"
  }
]
```

### Langkah 3: Skrip Pengujian CI Otomatis

Buat file `hands-on/m02/ci/run-ci-validation.ps1`:
```powershell
[CmdletBinding()]
param (
    [Parameter(Mandatory=$false)]
    [string]$ModelFolder = "$PSScriptRoot/../src/SalesAnalytics.SemanticModel",
    [Parameter(Mandatory=$false)]
    [string]$RulesFile = "$PSScriptRoot/bpa-rules.json"
)

Write-Host "=== Memulai Validasi CI Semantic Model ===" -ForegroundColor Cyan

# 1. Verifikasi Eksistensi File
if (-not (Test-Path $ModelFolder)) {
    Write-Error "Folder semantic model tidak ditemukan: $ModelFolder"
    exit 1
}

# 2. Periksa Format TMDL Syntax Secara Programmatic
Write-Host "[1/2] Memvalidasi Integritas TMDL Directory..." -ForegroundColor Yellow
$tmdlFiles = Get-ChildItem -Path $ModelFolder -Filter "*.tmdl" -Recurse
Write-Host "Ditemukan $($tmdlFiles.Count) file definisi TMDL." -ForegroundColor Green

# 3. Dummy Runner untuk BPA (Bisa dipadukan dengan TE2/TE3 binary jika terinstal)
Write-Host "[2/2] Membaca Aturan BPA dari: $RulesFile" -ForegroundColor Yellow
$rules = Get-Content $RulesFile | ConvertFrom-Json
Write-Host "Berhasil memuat $($rules.Count) aturan kepatuhan arsitektur." -ForegroundColor Green

# Lakukan pengecekan statis sederhana terhadap formatString measure
$violations = 0
foreach ($file in $tmdlFiles) {
    $content = Get-Content $file.FullName -Raw
    if ($content -match "measure\s+'([^']+)'\s*=") {
        $measureName = $matches[1]
        if ($content -notmatch "formatString:") {
            Write-Warning "Pelanggaran BPA (Severity 1): Measure '$measureName' di $($file.Name) tidak memiliki 'formatString'!"
            $violations++
        }
    }
}

if ($violations -gt 0) {
    Write-Error "Validasi CI GAGAL: Terdeteksi $violations pelanggaran aturan arsitektur!"
    exit 1
}

Write-Host "=== Validasi CI Berhasil: Seluruh standar arsitektur terpenuhi ===" -ForegroundColor Green
exit 0
```

---

## 13. Exercise

### Level Easy
Modifikasi file `FactSales.tmdl` pada praktikum di atas:
- Tambahkan measure baru: `Average Sales Per Order`.
- Pastikan menyertakan sintaks `formatString` yang benar.
- Jalankan skrip `run-ci-validation.ps1` dan pastikan pipeline menghasilkan exit code 0.

### Level Medium
Buat sebuah skrip PowerShell bernama `test-dax-queries.ps1` yang mengeksekusi query DAX berikut menggunakan koneksi ADOMD/XMLA terhadap Semantic Model lokal atau remote:
```dax
EVALUATE
SUMMARIZECOLUMNS(
    "TotalRevenue", [Gross Sales],
    "TxCount", [Total Transactions]
)
```
Skrip harus memvalidasi bahwa kolom `TotalRevenue` tidak bernilai `BLANK()` atau bernilai `0`. Jika `0`, hentikan eksekusi dengan return code 1.

### Level Hard
Implementasikan skrip PowerShell TOM (`Microsoft.AnalysisServices.Tabular`) yang dapat melakukan proses **Partisi Dinamis**:
1. Skrip memeriksa apakah partisi `FactSales-2026-Q1` sudah ada di model Analysis Services remote.
2. Jika belum ada, buat partisi baru dengan query source M yang dibatasi pada range tanggal kuartal tersebut secara otomatis.
3. Refresh hanya partisi baru tersebut (`ProcessData`) tanpa me-refresh partisi historis lainnya.

---

## 14. Challenge

### Skenario: Arsitektur Zero-Downtime Blue/Green Semantic Model Deployment
Sebuah bank investasi menjalankan aplikasi analitik trading frekuensi tinggi yang membaca Semantic Model secara konstan via Direct Lake / In-Memory. Tenant admin tidak mengizinkan adanya *read-lock* lebih dari 2 detik selama deployment versi terbaru.

**Tugas Anda:**
Rancang arsitektur deployment otomatis (menggunakan Azure DevOps YAML, PowerShell, dan Service Principal) yang:
1. Men-deploy model baru dengan nama sementara `SalesAnalytics_Green` di workspace yang sama.
2. Melakukan *data processing* penuh pada model Green secara paralel tanpa mengganggu model `SalesAnalytics_Blue` (model aktif saat ini).
3. Melakukan *smoke testing* otomatis (eksekusi 5 query DAX mission-critical).
4. Melakukan penukaran (*traffic cut-over / swap*) secara instan dengan mengubah metadata target koneksi laporan tanpa disadari oleh ribuan pengguna aktif.
5. Menghapus atau menonaktifkan model lama (`Blue`) jika cut-over berhasil, atau melakukan *instant rollback* jika pengujian pasca-deploy mengalami kegagalan.

*Tuliskan dokumen arsitektur teknis ringkas dan skrip orkestrasi PowerShell utamanya.*

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. **Mengapa file biner `.pbix` tidak disarankan untuk digunakan sebagai artefak utama dalam sistem Version Control seperti Git?**
   - *Jawaban*: Karena `.pbix` adalah arsip biner terkompresi. Git tidak dapat melakukan kalkulasi baris per baris (*line-by-line diff*), sehingga memicu konflik biner yang tidak dapat digabungkan (*unresolvable merge conflict*) saat dikerjakan oleh lebih dari satu developer.
2. **Apa ekstensi file metadata teks baru yang memecah struktur semantic model secara modular?**
   - *Jawaban*: TMDL (*Tabular Model Definition Language*), yang menyimpan definisi model dalam file teks individual berekstensi `.tmdl`.
3. **Protokol/port jaringan apa yang digunakan untuk komunikasi langsung tingkat rendah (read/write metadata) dengan mesin VertiPaq di Power BI Premium?**
   - *Jawaban*: XMLA Endpoint (menggunakan protokol MS-SSAS over HTTP/HTTPS).
4. **Apa fungsi utama dari Tabular Editor Best Practice Analyzer (BPA) dalam pipeline CI?**
   - *Jawaban*: Berfungsi sebagai linter/analisis statis kode untuk mendeteksi pelanggaran performa DAX, inkonsistensi penamaan, redundansi kolom, dan kesalahan konfigurasi model sebelum kode di-deploy.
5. **Level izin minimum apa yang harus dimiliki oleh Service Principal di dalam Fabric Workspace untuk dapat melakukan deployment metadata via XMLA?**
   - *Jawaban*: Minimal role **Contributor** (direkomendasikan **Member** atau **Admin** untuk manipulasi permission dan credential refresh).

### 15.2 Pertanyaan Intermediate
1. **Bagaimana mekanisme TMDL mencegah timpa-menimpa kode (*code overwrites*) pada measure saat dua developer bekerja secara bersamaan?**
   - *Jawaban*: TMDL memisahkan definisi tabel ke dalam file independen (`NamaTabel.tmdl`). Selama kedua developer memodifikasi measure pada tabel yang berbeda, perubahannya tercatat pada file teks terpisah sehingga Git dapat melakukan *merge* secara otomatis tanpa konflik. Jika mereka memodifikasi tabel yang sama, perubahan tetap berbentuk teks sehingga *diff engine* bawaan Git dapat menyelesaikan penggabungan baris kode.
2. **Mengapa metadata deployment via XMLA jauh lebih cepat dibandingkan upload file `.pbix` via REST API standard?**
   - *Jawaban*: Metadata deployment via XMLA/TOM hanya mengirimkan payload instruksi DDL skema model tabular ke Analysis Services tanpa menyertakan payload data fisik, dan tidak secara otomatis menghapus cache partisi data eksisting yang tidak mengalami perubahan skema.
3. **Mengapa kredensial gateway/data source hilang atau invalid setelah database Tabular dideploy melalui skrip XMLA?**
   - *Jawaban*: Spesifikasi XMLA/TMSL sengaja menolak atribut kredensial keamanan demi perlindungan informasi rahasia. Kredensial harus diatur secara terpisah pasca-deployment menggunakan Power BI REST API atau konfigurasi gateway terikat.
4. **Apa perbedaan mendasar antara Fabric Deployment Pipeline native dengan Azure DevOps Custom CI/CD Pipeline?**
   - *Jawaban*: Fabric Deployment Pipeline adalah orchestrator berbasis UI di Power BI Portal untuk mempromosikan artefak antar workspace yang terhubung tanpa perlu mengelola build agent. Sedangkan Azure DevOps Pipeline adalah orkestrator eksternal code-first yang memberikan fleksibilitas penuh untuk eksekusi skrip kustom, integrasi testing pihak ketiga (seperti Tabular Editor CLI, NBI, Python), dan pengujian gating otomatis yang ketat.
5. **Bagaimana cara mengisolasi data confidential pada saat developer lokal menguji file PBIP di komputernya masing-masing?**
   - *Jawaban*: Menggunakan parameter Power Query M (misal: `Environment = "Dev"`) yang membatasi pengambilan data ke subset lokal/mock data, atau menggunakan row-level security (RLS) serta memastikan data cache lokal tidak dimasukkan ke dalam version control.

### 15.3 Skenario Kasus Produksi
1. **Skenario Kasus 1**:
   *Sebuah pipeline CI/CD Azure DevOps mengalami kegagalan pada tahap validasi BPA Tabular Editor dengan pesan kesalahan: `[Rule: PERF_AVOID_BIAXIAL_RELATIONSHIPS] Found bidirectional cross-filtering on relationship between FactOrders and DimCustomer`.*
   - **Pertanyaan**: Apa dampak performa dari aturan ini di lingkungan produksi, dan tindakan apa yang harus diambil oleh BI developer dalam kode TMDL-nya?
   - **Analisis/Solusi**: Relasi dua arah (*bidirectional cross-filtering*) dapat menyebabkan ambiguitas jalur evaluasi filter, memicu pemindaian tabel besar yang tidak perlu di VertiPaq, dan menurunkan performa query DAX secara signifikan. Developer harus mengubah properti relasi di file `relationships.tmdl` dari `crossFilteringBehavior: bothDirections` menjadi `crossFilteringBehavior: oneDirection`, serta menyelesaikan kebutuhan kalkulasi spesifik menggunakan fungsi `CROSSFILTER()` di tingkat measure saja.
2. **Skenario Kasus 2**:
   *Setelah mempromosikan semantic model dari UAT ke Production menggunakan TOM script, laporan visual menunjukkan error `An error occurred while evaluating the query: Partition does not contain data`.*
   - **Pertanyaan**: Apa yang menyebabkan partisi kosong ini pasca XMLA deploy, dan bagaimana langkah remediasi otomatis dalam pipeline?
   - **Analisis/Solusi**: Model dideploy sebagai entitas baru atau skema partisi baru dibuat di Production tanpa mengeksekusi *refresh command*. Remediari: Tambahkan task otomatis pasca-deploy di pipeline yang memanggil Power BI REST API `/refreshes` dengan payload tipe refresh `selective` (atau via TOM `Model.Tables["FactOrders"].Partitions["P_New"].RequestRefresh(RefreshType.DataOnly)` lalu `Commit()`).
3. **Skenario Kasus 3**:
   *Developer mengganti nama kolom dari `CustomerKey` menjadi `CustomerID` di semantic model. Deployment CI/CD berhasil, namun semua laporan produksi yang terhubung ke semantic model tersebut langsung rusak (*broken visuals*).*
   - **Pertanyaan**: Bagaimana arsitektur deployment pipeline modern mencegah *breaking changes* semacam ini menjangkau lingkungan produksi?
   - **Analisis/Solusi**: Pipeline harus memiliki tahap *Dependency & Impact Analysis*. Hal ini dapat dicapai dengan memanfaatkan script validasi yang memanggil Power BI Scanner API untuk mendeteksi laporan mana saja yang bergantung pada field tersebut, atau menjalankan integration test headless (menggunakan Playwright atau Power BI Embedded REST API test) terhadap laporan UAT sebelum izin promosi ke Production diberikan (*Approval Gate* ditolak jika visual error terdeteksi).

---

## 16. Summary
Modul ini telah membedah arsitektur enterprise Power BI DevOps dan Automated ALM:
- **TMDL & PBIP** mentransformasi pengembangan analitik dari proses manual berbasis file biner monolitik menjadi rekayasa perangkat lunak deklaratif berbasis teks yang ramah terhadap kontrol versi Git.
- **Continuous Integration (CI)** dijamin melalui otomatisasi headless Tabular Editor Best Practice Analyzer (BPA) yang menyaring regresi performa dan DAX anti-patterns sebelum kode dapat di-merge.
- **Continuous Deployment (CD)** melalui **XMLA Endpoint & TOM** memungkinkan *metadata-only updates* secara aman dan instan tanpa membebani kapasitas komputasi dengan full refresh yang tidak perlu.
- Mengombinasikan pipeline Azure DevOps/GitHub Actions dengan tata kelola izin Service Principal menghasilkan ekosistem BI enterprise yang skalabel, stabil, terukur, dan memiliki audit trail yang patuh terhadap standar regulasi enterprise modern.