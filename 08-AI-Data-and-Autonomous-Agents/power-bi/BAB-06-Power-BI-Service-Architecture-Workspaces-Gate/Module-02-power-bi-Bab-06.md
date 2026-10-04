# BAB-06: Power BI Service Architecture, Workspaces & On-Premises Data Gateway
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Merancang dan mengoperasikan arsitektur *High Availability* (HA) serta *Load Balancing* pada On-Premises Data Gateway Cluster skala enterprise.
- Mengonfigurasi dan mengoptimasi *Mashup Engine* (`Microsoft.Mashup.Container`) pada node gateway untuk menangani beban *concurrency* tinggi dan mencegah saturasi memori (*Out Of Memory*).
- Mengotomatisasi siklus hidup *workspace*, *gateway binding*, dan *deployment pipeline* menggunakan Power BI REST API, PowerShell (`MicrosoftPowerBIMgmt`), dan *Service Principal* dalam skenario CI/CD.
- Mendiagnosis serta merekayasa integrasi konektivitas hibrida yang aman menggunakan *Azure Service Bus Relay*, *Private Endpoints*, dan *Kerberos Constrained Delegation* (KCD) untuk DirectQuery RLS.
- Mengimplementasikan pemantauan performa gateway tingkat lanjut menggunakan *Performance Counters*, *Log Analytics*, dan *Gateway Logs* guna mendeteksi *bottleneck* sebelum berdampak pada SLA produksi.

---

### 2. Prerequisite

Untuk memahami materi ini secara mendalam, peserta wajib menguasai:
- **Jaringan & Keamanan:** Konsep TCP/IP, TLS 1.2/1.3, Proxy, Azure ExpressRoute/Site-to-Site VPN, port outbound Azure Service Bus (5671, 5672, 443), Active Directory Domain Services (AD DS), SPN (*Service Principal Name*), dan *Kerberos Constrained Delegation*.
- **Cloud Identity:** Konfigurasi Microsoft Entra ID (Azure AD), registrasi Enterprise Application/App Registration, *Client Secret/Certificate*, dan pemberian hak konsentrasi API (*Tenant-level consent*).
- **Power BI Foundation:** Penguasaan mode koneksi (DirectQuery vs. Import), struktur model semantik, serta pemahaman dasar Power BI Service Architecture (Bab 06 Modul 01).
- **Automasi:** Kemampuan eksekusi PowerShell Core 7.x, scripting Bash, dan manipulasi payload REST API berbasis JSON.

---

### 3. Concept & Internal Architecture

#### 3.1. Arsitektur Komunikasi Gateway & Azure Relay Mechanism
On-Premises Data Gateway **tidak menerima koneksi inbound** dari internet publik. Ini mengeliminasi kebutuhan membuka port masuk pada firewall on-premises Anda atau menempatkan gateway di zona DMZ tanpa perlindungan. 

Mekanisme komunikasi internal bekerja sebagai berikut:
1. Saat service *On-Premises Data Gateway* (`EnterpriseGatewayService`) berjalan pada host lokal, ia membuka socket keluar (*outbound persistent connection*) ke **Azure Service Bus Relay**.
2. Power BI Cloud Service (melalui *Query Processing Engine* di dalam Fabric/Power BI Cloud Tenant) menghasilkan query (DAX atau SQL) dan mendepositkan *work request* ke antrean Azure Service Bus yang terenkripsi.
3. Node gateway lokal melakukan *long polling* ke Azure Relay untuk mengambil antrean pekerjaan tersebut.
4. Payload query didekripsi secara lokal menggunakan kunci privat gateway (*Gateway Recovery Key* yang diasosiasikan saat inisialisasi kluster).
5. Gateway meneruskan query ke data source lokal (misalnya: SQL Server, Oracle, SAP HANA) melalui protokol native data source (TCP 1433, TCP 1521, TCP 30015).
6. Data source memproses query dan mengembalikan *result set* ke gateway.
7. Gateway melakukan kompresi, enkripsi data, dan streaming balik ke Power BI Service melalui koneksi outbound TLS 1.2 yang telah terbuka sebelumnya.

```
+-----------------------------------------------------------------------------------------+
|                                    POWER BI SERVICE                                      |
|  [Power BI Report / Dashboard] <---> [Semantic Model Engine (AS Azure)]                |
|                                                     |                                   |
|                                         (HTTPS Query Generation)                        |
|                                                     v                                   |
|                                         [Gateway Cloud Service]                         |
+-----------------------------------------------------|-----------------------------------+
                                                      | Outbound Request
                                                      v (HTTPS / AMQP)
                                     +----------------------------------+
                                     |    Azure Service Bus Relay       |
                                     | (Encrypted Queue & Orchestration)|
                                     +----------------------------------+
                                                      ^
                                                      | Outbound Long Polling
+-----------------------------------------------------|-----------------------------------+
| ON-PREMISES ENTERPRISE NETWORK                      | (TCP 443 / 5671-5672)             |
|                                                     v                                   |
|  +-----------------------------------------------------------------------------------+  |
|  |                       ON-PREMISES DATA GATEWAY CLUSTER                            |  |
|  |                                                                                   |  |
|  |  +------------------------------+             +--------------------------------+  |  |
|  |  | Node 1 (Primary / Active)    |             | Node 2 (Load Balanced)         |  |  |
|  |  |                              |             |                                |  |  |
|  |  | [EnterpriseGatewayService]   |             | [EnterpriseGatewayService]     |  |  |
|  |  |          | (IPC)             |             |          | (IPC)               |  |  |
|  |  |          v                   |             |          v                     |  |  |
|  |  | [Mashup Engine Containers]   |             | [Mashup Engine Containers]     |  |  |
|  |  +------------------------------+             +--------------------------------+  |  |
|  |                 |                                             |                   |  |
|  +-----------------|---------------------------------------------|-------------------+  |
|                    v                                             v                      |
|       [Local Native Protocols: TDS (1433), SQL*Net (1521), RFC/HANA (30015)]            |
|                    |                                             |                      |
|                    +----------------------+----------------------+                      |
|                                           v                                             |
|                             +---------------------------+                               |
|                             | Enterprise Data Sources   |                               |
|                             | (SQL, Oracle, SAP, NAS)   |                               |
|                             +---------------------------+                               |
+-----------------------------------------------------------------------------------------+
```

#### 3.2. Lifecycle Eksekusi Mashup Engine Container
Setiap kali Gateway memproses pembaruan data (*scheduled refresh*) atau eksekusi DirectQuery, Gateway Service tidak mengeksekusi transformasi M secara langsung di dalam proses utamanya demi isolasi stabilitas. Sebaliknya, gateway menggunakan proses *out-of-process worker*:
- **File Eksekusi:** `Microsoft.Mashup.Container.NetFX45.exe` (atau varian 64-bit runtime).
- **Proses Pooling:** Gateway mempertahankan sejumlah *mashup container* di dalam *pool* memori. Saat query masuk, container diambil dari pool, mengeksekusi query M, mengonversi data ke format *ADR Stream* (*Analysis Services Data Reader*), dan mengembalikannya ke service utama.
- **Isolasi Kegagalan:** Jika satu transformasi data mengalami crash (*out-of-memory* atau driver native rusak), hanya container tersebut yang mati (`ExitCode != 0`). Proses `EnterpriseGatewayService` tetap hidup melayani query lain.

#### 3.3. Gateway High Availability & Load Balancing Logic
Ketika beberapa node digabungkan ke dalam satu cluster:
- **Pemberian Beban (Distribusi Query):** Gateway mendistribusikan query berdasarkan pembobotan sumber daya CPU dan memori jika opsi *Distribute requests across all active gateways in this cluster* diaktifkan. Jika tidak diaktifkan, node sekunder murni berfungsi sebagai *passive failover*.
- **Health Probing:** Node utama dan sekunder terus mengirimkan *heartbeat* ke Gateway Cloud Service. Jika satu node gagal merespons *heartbeat* dalam durasi tertentu (umumnya 2 hingga 3 kali interval polling), Azure Service Bus Relay menandai node tersebut *offline* dan segera mengalihkan seluruh traffic antrean ke node yang sehat tanpa intervensi manual.

---

### 4. Why & What

| Dimensi | Mengapa Diperlukan (Why) | Apa Objek Teknisnya (What) |
| :--- | :--- | :--- |
| **Availability** | Mencegah downtime pelaporan eksekutif saat gateway host mengalami patching OS atau crash hardware. | **Gateway Cluster HA**: Konfigurasi multi-node (N+1) terkoordinasi via Cloud Orchestrator. |
| **Throughput & Concurrency** | Mencegah bottleneck eksekusi DirectQuery saat ratusan concurrent user mengakses dashboard visual secara simultan. | **Load Balancing & Mashup Container Pooling Configuration**. |
| **Enterprise Governance** | Menghilangkan human-error dalam deployment model, permission binding, dan konfigurasi kredensial gateway. | **Service Principal-driven CI/CD Pipelines** via REST API & Fabric Deployment Pipelines. |
| **Keamanan Identitas** | Mencegah *credential leakage* dan menegakkan Row-Level Security (RLS) di level database lokal tanpa sinkronisasi password. | **Kerberos Constrained Delegation (KCD)** dengan DirectQuery Single Sign-On (SSO). |
| **Observability** | Mendeteksi kueri yang lambat, spooling disk yang membengkak, dan memori yang bocor sebelum gateway hang. | **Gateway Log Analytics Integration** & Windows Performance Monitor Counters. |

---

### 5. How (Workflow Detail)

#### Workflow Integrasi Produksi: Gateway Cluster, Workspace Governance & CI/CD Binding

```
[Developer commit Git] 
        |
        v
[Azure DevOps / GitHub Actions Pipeline]
        |
        +---> Step 1: Eksekusi PBI Inspector / Tabular Editor (Linter & Model Validation)
        |
        +---> Step 2: Deploy Semantic Model (.bim / PBIX) via Service Principal ke Workspace Produksi
        |
        +---> Step 3: Panggil API "Get Gateways" -> Dapatkan Gateway Cluster ID
        |
        +---> Step 4: Panggil API "Get Datasources" -> Dapatkan Datasource ID di Gateway
        |
        +---> Step 5: Panggil API "Bind To Gateway" -> Bind Dataset ke Gateway Datasource
        |
        +---> Step 6: Trigger Dataset Refresh via POST Call
        |
        +---> Step 7: Polling Status Refresh hingga "Completed"
```

1. **Inisialisasi Cluster Gateway:** Host primer diinstal menggunakan installer enterprise resmi. Pada langkah recovery, admin mendefinisikan *Gateway Recovery Key* yang kuat (disimpan di Azure Key Vault). Host sekunder diinstal, memilih opsi *"Add to an existing gateway cluster"*, dan diotentikasi menggunakan recovery key yang sama.
2. **Kustomisasi Konfigurasi Mesin Mashup:** Mengedit `Microsoft.PowerBI.DataMovement.Pipeline.GatewayCore.dll.config` untuk menetapkan batas container pool dan ambang batas alokasi memori lokal.
3. **Penyediaan Service Principal:** Membuat App Registration di Entra ID, memberikan permission `Tenant.ReadWrite.All` atau menugaskannya ke Security Group khusus yang diizinkan menggunakan Power BI Service Read/Write Admin APIs.
4. **Automasi CI/CD:** Script pipeline (PowerShell/REST) mendeteksi workspace target, memvalidasi koneksi data source ke gateway, memetakan *Connection String* pada file konfigurasi model semantik, mengeksekusi binding, dan memverifikasi kesehatan koneksi secara terprogram.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengiriman Logistik Terisolasi (Gateway sebagai Agen Lapangan)
Bayangkan sebuah bank dengan brankas bawah tanah berkeamanan super-ketat (On-Premises Database). Bank ini tidak memiliki pintu masuk atau interkom dari luar gedung. 

- **Azure Service Bus Relay** adalah sebuah loket *drop-box* netral yang terletak di kantor pos pusat kota (Cloud).
- **Gateway Host** adalah kurir resmi bank tersebut. Setiap 1 detik, kurir ini pergi dari brankas ke kantor pos untuk memeriksa apakah ada instruksi kerja di *drop-box* (**Outbound Polling**).
- Jika ada surat tugas (Kueri Analisis), kurir membawa surat itu ke ruang kerja internal brankas.
- Kurir tidak mengerjakannya sendiri; ia memberikan salinan tugas itu kepada tim juru hitung sementara (**Mashup Containers**).
- Tim juru hitung mengambil emas/dokumen dari brankas, menghitung dan membungkus hasilnya dalam kotak bersegel aman, lalu memberikannya kembali kepada kurir untuk diletakkan di kantor pos pusat, yang kemudian diambil oleh klien (Power BI Service).

#### Diagram Alur Data Mashup Container & Memory Spooling

```
                     +----------------------------------------+
                     |  EnterpriseGatewayService.exe (Parent) |
                     +----------------------------------------+
                                         |
               +-------------------------+-------------------------+
               | Inter-Process Communication (Named Pipes / Memory) |
               v                                                   v
+-------------------------------+               +-------------------------------+
| Mashup Container 1 (PID: 1042)|               | Mashup Container 2 (PID: 1088)|
| [Container Working Set Limit] |               | [Container Working Set Limit] |
|                               |               |                               |
| Read Buffer -> Transform ->   |               | Read Buffer -> Transform ->   |
| Spooling to Disk if RAM Full: |               | Spooling to Disk if RAM Full: |
| (%TEMP%\Microsoft\Mashup...)  |               | (%TEMP%\Microsoft\Mashup...)  |
+-------------------------------+               +-------------------------------+
               |                                                   |
               +-------------------------+-------------------------+
                                         v
               +---------------------------------------------------+
               | Target On-Premises Data Source (SQL, Teradata, etc)|
               +---------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Penyetelan Konfigurasi Resource Gateway
File: `C:\Program Files\On-premises data gateway\Microsoft.PowerBI.DataMovement.Pipeline.GatewayCore.dll.config`

Cuplikan konfigurasi XML tingkat lanjut untuk mengontrol konsumsi memori dan container concurrency:

```xml
<configuration>
  <appSettings>
    <!-- Jumlah maksimum proses mashup container simultan yang diizinkan -->
    <!-- Formula: (Jumlah Logical CPU Core * 2) - 1 -->
    <add key="MashupDefaultPoolContainerMaxCount" value="15" />

    <!-- Mengaktifkan spooling memori ke disk ketika mencapai persentase tertentu -->
    <add key="MashupMemoryThresholdPercentage" value="75" />

    <!-- Batas alokasi memori privat untuk satu container mashup tunggal (dalam Megabytes) -->
    <!-- Mencegah single query run-away menghabiskan seluruh RAM host -->
    <add key="MashupWorkingSetLimitMB" value="4096" />

    <!-- Menonaktifkan tracing verbose pada level produksi demi performa I/O -->
    <add key="GatewayTraceLevel" value="Error" />
  </appSettings>
</configuration>
```

#### 7.2. Practical Example: Otomasi Binding Semantic Model ke Gateway Menggunakan Service Principal via PowerShell

Script ini siap pakai di level pipeline CI/CD (misal: Azure DevOps Pipeline / GitHub Runner) untuk mengotomatisasi proses provisioning dan *binding* model semantik ke On-Premises Data Gateway Cluster tanpa interaksi UI.

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
    [guid]$WorkspaceId,

    [Parameter(Mandatory = $true)]
    [guid]$DatasetId,

    [Parameter(Mandatory = $true)]
    [string]$TargetGatewayClusterName
)

$ErrorActionPreference = "Stop"

Write-Host ">>> [INIT] Memulai autentikasi via Service Principal..." -ForegroundColor Cyan

# 1. Akuisisi Token Entra ID untuk Power BI REST API
$TokenEndpoint = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
$Body = @{
    grant_type    = "client_credentials"
    client_id     = $ClientId
    client_secret = $ClientSecret
    scope         = "https://analysis.windows.net/powerbi/api/.default"
}

$AuthResponse = Invoke-RestMethod -Uri $TokenEndpoint -Method Post -Body $Body
$Headers = @{
    "Authorization" = "Bearer $($AuthResponse.access_token)"
    "Content-Type"  = "application/json"
}

Write-Host ">>> [SUCCESS] Bearer token berhasil diakuisisi." -ForegroundColor Green

# 2. Ambil seluruh Gateway Clusters yang dapat diakses oleh Service Principal
Write-Host ">>> [RESOLVE] Mengambil metadata gateway clusters..." -ForegroundColor Cyan
$GatewaysUrl = "https://api.powerbi.com/v1.0/myorg/gateways"
$GatewaysResponse = Invoke-RestMethod -Uri $GatewaysUrl -Method Get -Headers $Headers

$TargetGateway = $GatewaysResponse.value | Where-Object { $_.name -eq $TargetGatewayClusterName }

if (-not $TargetGateway) {
    throw "Fatal: Gateway Cluster dengan nama '$TargetGatewayClusterName' tidak ditemukan atau Service Principal tidak memiliki hak akses!"
}

$GatewayId = $TargetGateway.id
Write-Host ">>> [FOUND] Gateway Target ID: $GatewayId" -ForegroundColor Green

# 3. Ambil Unbound Datasources dari Semantic Model yang ditargetkan
Write-Host ">>> [DISCOVERY] Memeriksa data sources pada dataset target..." -ForegroundColor Cyan
$DatasourcesUrl = "https://api.powerbi.com/v1.0/myorg/groups/$WorkspaceId/datasets/$DatasetId/Default.GetBoundGatewayDataSources"

try {
    $CurrentSources = Invoke-RestMethod -Uri $DatasourcesUrl -Method Get -Headers $Headers
    Write-Host ">>> Dataset saat ini telah terhubung ke datasource ID: $($CurrentSources.value.id)" -ForegroundColor Yellow
} catch {
    Write-Host ">>> Dataset belum terikat ke gateway manapun, melanjutkan proses binding..." -ForegroundColor Gray
}

# 4. Bind Dataset ke Gateway Cluster
Write-Host ">>> [BINDING] Mengikat Semantic Model ($DatasetId) ke Gateway Cluster ($GatewayId)..." -ForegroundColor Cyan
$BindUrl = "https://api.powerbi.com/v1.0/myorg/groups/$WorkspaceId/datasets/$DatasetId/Default.BindToGateway"

$BindPayload = @{
    gatewayObjectId = $GatewayId
} | ConvertTo-Json

Invoke-RestMethod -Uri $BindUrl -Method Post -Headers $Headers -Body $BindPayload

Write-Host ">>> [SUCCESS] Dataset berhasil di-bind ke Gateway Cluster." -ForegroundColor Green

# 5. Memicu Test Refresh Data Asinkron
Write-Host ">>> [REFRESH] Memicu eksekusi refresh model semantik..." -ForegroundColor Cyan
$RefreshUrl = "https://api.powerbi.com/v1.0/myorg/groups/$WorkspaceId/datasets/$DatasetId/refreshes"
$RefreshPayload = @{
    notifyOption = "MailOnFailure"
} | ConvertTo-Json

Invoke-RestMethod -Uri $RefreshUrl -Method Post -Headers $Headers -Body $RefreshPayload
Write-Host ">>> [COMPLETED] Refresh terpicu di Power BI Service secara non-blocking." -ForegroundColor Green
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Skala Kasus
Sebuah institusi perbankan tier-1 mengoperasikan sistem *Core Banking* berbasis database relasional terdistribusi on-premises (Oracle Exadata & IBM DB2). Sebanyak 45.000 karyawan cabang mengakses dashboard performa pinjaman dan transaksi harian.

- **Karakteristik Data:** DirectQuery aktif, 1.200 visual request per detik pada jam sibuk (09:00 - 11:00 pagi).
- **Masalah Awal:** Gateway sering *hang*, latensi kueri melonjak dari 1,2 detik menjadi 35 detik, CPU host gateway menyentuh 100%, dan terjadi kegagalan acak bertuliskan *"The gateway is either offline or unreachable"*.

#### Solusi Arsitektur
1. **Topologi Fisik Gateway Cluster:**
   - Dibangun 4 node Gateway dedicated (Spesifikasi per node: VM Azure Stack/VMware 16 vCPU, 64 GB RAM, Enterprise SSD via NVMe over Fabrics).
   - Seluruh node ditempatkan di subnet internal yang sama dengan rute ExpressRoute berkecepatan tinggi ke Azure Service Bus Relay.
2. **Gateway Load Balancing Engine:**
   - Opsi `Distribute requests across all active gateways` diaktifkan di admin portal.
3. **Penyetelan Konfigurasi Mashup:**
   - Parameter `MashupWorkingSetLimitMB` dikunci pada 6144 MB per container.
   - `MashupDefaultPoolContainerMaxCount` diatur ke 24.
   - Mengalihkan temporary Mashup Spooling directory dari drive `C:\` ke dedicated High-IOPS NVMe drive `D:\PBI_Spool`.
4. **Implementasi DirectQuery SSO via Kerberos:**
   - Mengonfigurasi Service Principal Name (SPN) untuk service account gateway (`svc_pbigateway`).
   - Menerapkan *Kerberos Constrained Delegation* (KCD) dengan protokol transition (`UseProtocolTransition = $true`) untuk memetakan UPN akun Azure AD (email bank) ke sAMAccountName lokal database Active Directory.
5. **Observability Telemetry:**
   - Mengintegrasikan gateway performance counters secara periodik ke Azure Log Analytics workspace untuk melacak counter `Avg Gateway CPU %`, `Active Mashup Engine Count`, dan `Azure Relay Socket Handshake Latency`.

#### Hasil & Metrik Keberhasilan
- Latensi P95 kueri visual turun drastis dari 35 detik ke 1,8 detik.
- CPU utilization terdistribusi stabil di angka 45% - 60% merata di 4 node.
- Kegagalan query rontok hingga 0% (*Zero Gateway Unreachable Incidents*) selama audit kuartalan.

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Kerugian & Konsekuensi | Skenario Ideal |
| :--- | :--- | :--- | :--- |
| **On-Premises Data Gateway Clustering** | Mengeliminasi SPOF (*Single Point of Failure*), auto-failover, mendukung load balancing, kompatibel dengan sumber data lokal legacy. | Memerlukan manajemen hardware/OS on-prem, pembaruan versi manual/semi-otomatis bulanan, overhead konfigurasi firewall internal. | Akses ke sumber data on-premises (Oracle, DB2, Network File Shares) yang tidak terekspos ke cloud. |
| **Virtual Network (VNet) Data Gateway** | Bebas manajemen infrastruktur (PaaS), otomatis diskalakan oleh Microsoft, terintegrasi native dengan Azure VNet via subnet delegation. | Hanya mendukung data source yang bisa dicapai via Azure VNet, tidak mendukung data source lokal non-VNet (kecuali lewat VPN/ER), kapabilitas kustomisasi Mashup Engine terbatas. | Arsitektur data lakehouse/data warehouse berbasis Azure (Azure SQL, Synapse, Snowflake di Azure, Fabric). |
| **DirectQuery Mode via Gateway** | Zero-latency data ingestion (data selalu realtime), memori kapasitas cloud tidak terbebani data cache yang besar. | Menghasilkan beban I/O tinggi langsung ke database operasional on-premises; latensi rendering visual bergantung pada kecepatan database dan round-trip network. | Kebutuhan analitik near-real-time dan kepatuhan data residence ketat (data tidak boleh keluar dari server lokal). |
| **Import Mode (Scheduled Refresh) via Gateway** | Performa analitik visual super cepat (karena query dilayani oleh engine in-memory VertiPaq Power BI Service), mengurangi beban data source operasional. | Refresh terjadwal memakan bandwidth besar sekaligus saat ekstraksi; konsumsi RAM host gateway tinggi selama proses ekstraksi dan kompresi M-Engine. | Data analitik historis, dashboard agregat harian/mingguan yang tidak memerlukan sinkronisasi detik-demi-detik. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kerberos Constrained Delegation (KCD) Double-Hop Failure
- **Gejala:** Error bertuliskan `"We cannot generate a user credential"` atau `"NTLM authentication failed"` saat DirectQuery SSO diaktifkan.
- **Penyebab:** Service account gateway (`svc_pbigateway`) tidak memiliki delegasi yang sah ke SPN target SQL/Database, atau terjadi ketidakcocokan format UPN antara Cloud Identity dan On-Premises AD.
- **Solusi:**
  1. Daftarkan SPN target secara eksplisit via `setspn`:
     ```cmd
     setspn -S MSSQLSvc/sqlprod01.corp.internal:1433 corp\svc_pbigateway
     ```
  2. Buka Active Directory Users and Computers -> Cari akun gateway -> Tab *Delegation* -> Pilih *"Trust this user for delegation to specified services only"* -> Pilih *"Use any authentication protocol"*.

#### 10.2. Disk Exhaustion Akibat Spooling Mesin Mashup
- **Gejala:** Seluruh proses refresh model semantik gagal mendadak dengan pesan `"There is not enough space on the disk"`. Host gateway tidak merespons.
- **Penyebab:** Mesin Mashup menampung baris data yang belum diindeks ke disk lokal (`%TEMP%`) saat Import Mode memproses tabel ratusan juta baris tanpa *query folding*.
- **Solusi:** 
  1. Arahkan direktori spooling sementara ke drive disk khusus dengan menambahkan/mengubah variabel lingkungan sistem:
     ```powershell
     [Environment]::SetEnvironmentVariable("TEMP", "D:\PBI_Temp", "Machine")
     [Environment]::SetEnvironmentVariable("TMP", "D:\PBI_Temp", "Machine")
     ```
  2. Restart service `EnterpriseGatewayService`.
  3. Lakukan refactor pada model M untuk memastikan terjadi *Full Query Folding* sehingga kalkulasi dilakukan di server database, bukan di disk lokal gateway.

#### 10.3. TCP/IP Socket Exhaustion & Proxy Handshake Latency
- **Gejala:** Gateway log dipenuhi pesan kesalahan `System.Net.Sockets.SocketException: Only one usage of each socket address is normally permitted`.
- **Penyebab:** Ribuan DirectQuery requests membuka dan menutup koneksi HTTP/HTTPS keluar dalam waktu mikrodetik, meninggalkan port dalam status `TIME_WAIT`.
- **Solusi:**
  1. Ubah mode koneksi Gateway ke mode pengiriman socket langsung AMQP daripada HTTP. Buka aplikasi Gateway -> *Network* -> Aktifkan *Azure Relay Architecture mode: Direct TCP communication*.
  2. Lakukan tuning TCP registry pada Windows Server host:
     ```powershell
     Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters' -Name 'TcpTimedWaitDelay' -Value 30 -Type DWord
     Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters' -Name 'MaxUserPort' -Value 65534 -Type DWord
     ```

---

### 11. Best Practices (Production Checklist)

#### 11.1. Gateway Host Infrastructure Checklist
- [ ] Ditempatkan pada VM/Server dedicated, **bukan** pada server yang sama dengan Database Engine, Domain Controller, atau SSAS.
- [ ] Minimal 8 Physical/Virtual Cores (64-bit), 32 GB RAM per node untuk lingkungan medium-to-large.
- [ ] Konfigurasi minimal 2 node per cluster gateway demi redundansi *N+1*.
- [ ] Network adapter minimum 10 Gbps dengan koneksi direct/low-latency ke sumber data lokal (< 5ms round-trip).
- [ ] Drive sistem OS (`C:\`) terpisah dari drive untuk penampungan Gateway Spooling dan Log files.

#### 11.2. Networking & Security Checklist
- [ ] Firewall mengizinkan koneksi outbound ke port TCP 443, 5671, dan 5672 ke seluruh IP range `AzureCloud.<Region>` yang relevan.
- [ ] TLS Inspection / Deep Packet Inspection (DPI) pada firewall internal di-bypass/whitelisted untuk traffic gateway ke `*.servicebus.windows.net`, karena inspeksi TLS merusak socket relay enkripsi ganda Azure Service Bus.
- [ ] Service Account gateway berjalan di bawah *Managed Service Account* (gMSA) atau akun domain terdedikasi dengan privilege minimum (*Log on as a service* saja, bukan Domain/Local Admin).

#### 11.3. CI/CD & Governance Checklist
- [ ] Jangan pernah menggunakan akun pengguna perorangan (*User Principal*) untuk administrasi gateway produksi; gunakan Entra ID Service Principal.
- [ ] Recovery Key disimpan secara aman di dalam Enterprise Hardware Security Module (HSM) atau Azure Key Vault dengan akses terbatas.
- [ ] Gateway Client diperbarui secara rutin (maksimal N-2 dari versi rilis bulanan resmi Microsoft untuk menjaga kompatibilitas API cloud).

---

### 12. Hands-on Practice

Dalam praktikum ini, Anda akan menyusun struktur automasi enterprise untuk memeriksa kesehatan node gateway dan memetakan izin secara otomatis ke dalam workspace produksi.

#### Struktur Direktori Hands-on
Simpan file-file berikut di dalam direktori `hands-on/m02/`:
```
hands-on/m02/
├── 01_tune_gateway_config.ps1
├── 02_cluster_health_check.ps1
└── 03_pipeline_auto_binding.ps1
```

#### Langkah 1: Script Optimasi Host Config Gateway (`01_tune_gateway_config.ps1`)
Simpan script ini untuk mengotomatisasi penyesuaian file XML gateway host secara konsisten di seluruh node:

```powershell
# hands-on/m02/01_tune_gateway_config.ps1
param (
    [string]$ConfigPath = "C:\Program Files\On-premises data gateway\Microsoft.PowerBI.DataMovement.Pipeline.GatewayCore.dll.config",
    [int]$MaxContainers = 16,
    [int]$MemoryLimitMB = 4096,
    [int]$MemoryThresholdPercent = 80
)

if (-not (Test-Path -Path $ConfigPath)) {
    throw "Target konfigurasi tidak ditemukan pada path: $ConfigPath"
}

[xml]$ConfigXml = Get-Content -Path $ConfigPath

function Update-Or-Add-AppSetting([xml]$xmlDoc, [string]$key, [string]$value) {
    $node = $xmlDoc.configuration.appSettings.add | Where-Object { $_.key -eq $key }
    if ($node) {
        $node.value = $value
    } else {
        $newNode = $xmlDoc.CreateElement("add")
        $newNode.SetAttribute("key", $key)
        $newNode.SetAttribute("value", $value)
        $xmlDoc.configuration.appSettings.AppendChild($newNode) | Out-Null
    }
}

Update-Or-Add-AppSetting -xmlDoc $ConfigXml -key "MashupDefaultPoolContainerMaxCount" -value $MaxContainers.ToString()
Update-Or-Add-AppSetting -xmlDoc $ConfigXml -key "MashupWorkingSetLimitMB" -value $MemoryLimitMB.ToString()
Update-Or-Add-AppSetting -xmlDoc $ConfigXml -key "MashupMemoryThresholdPercentage" -value $MemoryThresholdPercent.ToString()

# Backup config lama
Copy-Item -Path $ConfigPath -Destination "$ConfigPath.bak_$(Get-Date -Format 'yyyyMMddHHmmss')"

# Simpan XML baru
$ConfigXml.Save($ConfigPath)

Write-Host "Konfigurasi Gateway berhasil dioptimasi. Harap restart 'EnterpriseGatewayService'." -ForegroundColor Green
```

#### Langkah 2: Audit Kesehatan Cluster Gateway via REST API (`02_cluster_health_check.ps1`)
Script ini digunakan untuk melakukan validasi cluster gateway apakah semua node berstatus sehat:

```powershell
# hands-on/m02/02_cluster_health_check.ps1
param (
    [Parameter(Mandatory = $true)] [string]$TenantId,
    [Parameter(Mandatory = $true)] [string]$ClientId,
    [Parameter(Mandatory = $true)] [string]$ClientSecret
)

$TokenUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
$TokenBody = @{
    grant_type    = "client_credentials"
    client_id     = $ClientId
    client_secret = $ClientSecret
    scope         = "https://analysis.windows.net/powerbi/api/.default"
}
$Token = (Invoke-RestMethod -Uri $TokenUrl -Method Post -Body $TokenBody).access_token
$Headers = @{ "Authorization" = "Bearer $Token"; "Content-Type" = "application/json" }

# Mengambil status Gateway Clusters
$Clusters = Invoke-RestMethod -Uri "https://api.powerbi.com/v1.0/myorg/gateways" -Headers $Headers -Method Get

$Report = foreach ($Cluster in $Clusters.value) {
    # Ambil detail status tiap node di dalam gateway
    $StatusUrl = "https://api.powerbi.com/v1.0/myorg/gateways/$($Cluster.id)/status"
    try {
        $Status = Invoke-RestMethod -Uri $StatusUrl -Headers $Headers -Method Get
        $ClusterStatus = "Online"
    } catch {
        $ClusterStatus = "Offline/Degraded"
    }

    [PSCustomObject]@{
        GatewayClusterId   = $Cluster.id
        GatewayClusterName = $Cluster.name
        Type               = $Cluster.type
        Status             = $ClusterStatus
    }
}

$Report | Format-Table -AutoSize
```

#### Langkah 3: Eksekusi Pengujian
1. Jalankan `01_tune_gateway_config.ps1` pada server lokal (buka PowerShell sebagai Administrator).
2. Buka Windows Services (`services.msc`), restart service **On-premises data gateway service**.
3. Jalankan `02_cluster_health_check.ps1` menggunakan kredensial Service Principal Anda untuk memastikan status cluster berstatus `Online`.

---

### 13. Exercise

#### 13.1. Easy Level
Tulis script PowerShell singkat untuk mengekstrak 50 baris terakhir dari file gateway error log di path direktori default `C:\Users\PBIEgwService\AppData\Local\Microsoft\On-premises data gateway\GatewayErrors*.log` dan filter hanya baris yang mengandung kode error `DM_GWPipeline_Gateway_DataSourceAccessError`.

#### 13.2. Medium Level
Buat sebuah script PowerShell yang mengevaluasi response time endpoint Azure Service Bus Relay dari host gateway lokal. Script harus mengetes konektivitas ke port 443, 5671, dan 5672 terhadap domain gateway Anda (`*.servicebus.windows.net`), menghitung latensi TCP handshake, dan mengembalikan status `PASS` jika latensi di bawah 150ms atau `ALERT` jika di atas 150ms.

#### 13.3. Hard Level
Rancang script automasi CI/CD lengkap yang menerima input parameter file konfigurasi JSON berisi:
- `WorkspaceName`
- `DatasetName`
- `TargetClusterName`
- `DatasourceConnectionString`

Script harus:
1. Menemukan Workspace ID dan Dataset ID berdasarkan nama string.
2. Memeriksa apakah Datasource Connection String sudah terdaftar di Gateway Cluster tersebut.
3. Jika belum, tambahkan datasource baru ke Gateway Cluster dengan tipe `SQL` menggunakan kredensial Windows yang dienkripsi.
4. Lakukan binding Dataset ke Datasource yang baru dibuat.
5. Tangani seluruh potensi kegagalan (HTTP 401, 403, 404, 500) dengan *exponential backoff retry policy*.

---

### 14. Challenge

#### Skenario: Arsitektur Gateway "Air-Gapped Proxy & Double Hop DMZ"
Sebuah lembaga pertahanan multinasional memiliki infrastruktur jaringan yang dibagi menjadi 3 zona keamanan ketat:
1. **Zona 1 (Data Core):** Server database SQL Server dan Teradata terisolasi tanpa akses internet sama sekali.
2. **Zona 2 (DMZ Internal):** Subnet perantara dengan *Squid Forward Proxy Server*. Hanya server di zona ini yang boleh mengakses internet keluar via Proxy, dengan enkripsi TLS termination yang sangat dibatasi.
3. **Zona 3 (Cloud Public):** Power BI Service / Fabric Tenant.

#### Persyaratan Desain Tantangan:
Rancang arsitektur implementasi On-Premises Data Gateway yang memenuhi kriteria berikut tanpa melanggar prinsip kepatuhan keamanan:
1. Gateway dipasang di Zona 2, namun database berada di Zona 1. Akses dari Zona 2 ke Zona 1 harus menggunakan Kerberos Constrained Delegation (KCD) lintas boundary domain Active Directory.
2. Seluruh traffic keluar dari Gateway ke Azure Relay harus dipaksa melewati Squid Proxy di Zona 2 tanpa memutus TLS tunnel (no man-in-the-middle decryption pada Azure Service Bus sockets).
3. Buat skema konfigurasi arsitektur jaringan secara detail:
   - Pengaturan konfigurasi proxy pada file `enterprisegateway.exe.config` lokal gateway.
   - Konfigurasi DNS dan routing.
   - Rencana mitigasi jika Squid Proxy server mengalami *failover* tiba-tiba tanpa menyebabkan data refresh antrean Power BI terhenti.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic (Pilihan Ganda)

1. **Port keluar (outbound) manakah yang secara default digunakan oleh On-Premises Data Gateway untuk komunikasi AMQP berkecepatan tinggi ke Azure Service Bus Relay?**
   - A. Port 80 & 8080
   - B. Port 1433 & 1521
   - C. Port 5671 & 5672
   - D. Port 3389 & 22

2. **File konfigurasi utama untuk mengatur alokasi memori dan batas maksimum container pool pada Gateway adalah:**
   - A. `web.config`
   - B. `Microsoft.PowerBI.DataMovement.Pipeline.GatewayCore.dll.config`
   - C. `MashupEngineSettings.json`
   - D. `PowerBIGatewayUpdater.exe.config`

3. **Mengapa On-Premises Data Gateway tidak memerlukan pembukaan port masuk (inbound) pada firewall internal?**
   - A. Karena data dikirim via satelit.
   - B. Karena gateway menggunakan persistent outbound connection ke Azure Service Bus Relay untuk menarik data (pull model).
   - C. Karena Power BI Service secara otomatis meretas port lokal menggunakan protokol UPnP.
   - D. Karena model DirectQuery tidak memerlukan gateway.

4. **Proses eksekutabel Windows manakah yang bertindak sebagai worker container terisolasi untuk memproses transformasi Power Query (M)?**
   - A. `EnterpriseGatewayService.exe`
   - B. `System.Data.SqlClient.exe`
   - C. `Microsoft.Mashup.Container.NetFX45.exe`
   - D. `PowerBIDesktop.exe`

5. **Apa fungsi utama dari Gateway Recovery Key pada saat instalasi awal?**
   - A. Menghapus seluruh data source di cloud.
   - B. Mengenkripsi kredensial data source secara lokal dan menambahkan node baru ke cluster gateway yang sama.
   - C. Mengubah lisensi Power BI Pro menjadi Premium.
   - D. Mengaktifkan fitur preview mingguan pada gateway.

---

#### Bagian B: Intermediate (Pilihan Ganda / Benar-Salah)

6. **Benar atau Salah:** Saat mengaktifkan opsi *"Distribute requests across all active gateways in this cluster"*, Azure Cloud Service akan mendistribusikan kueri secara round-robin buta tanpa memperhitungkan beban metrik CPU atau ketersediaan memori node gateway.
   - A. Benar
   - B. Salah

7. **Dalam DirectQuery Single Sign-On (SSO) menggunakan Kerberos, atribut apakah yang harus disinkronkan antara identitas Microsoft Entra ID cloud dan On-Premises Active Directory?**
   - A. User Principal Name (UPN)
   - B. Employee Badge Number
   - C. User Password Hash
   - D. Security Identifier (SID) lokal

8. **Apa dampak utama jika parameter `MashupWorkingSetLimitMB` tidak didefinisikan (diatur ke 0 atau unbounded) pada lingkungan dengan banyak refresh dataset paralel?**
   - A. Kecepatan refresh akan selalu meningkat dua kali lipat.
   - B. Satu query yang kompleks dapat mengonsumsi seluruh sisa RAM pada host, memicu Out-of-Memory (OOM) dan merusak stabilitas container lain.
   - C. Gateway secara otomatis memindahkan beban ke memori GPU.
   - D. Port TCP 443 akan ditutup secara otomatis oleh OS.

9. **Jika suatu perusahaan ingin menghubungkan Power BI Service ke Azure SQL Managed Instance di dalam Azure VNet pribadi tanpa mengelola VM IaaS Windows Server sama sekali, solusi gateway apakah yang paling arsitektural dan hemat maintenance?**
   - A. On-Premises Data Gateway Personal Mode
   - B. Azure Data Factory Self-Hosted Integration Runtime
   - C. Virtual Network (VNet) Data Gateway
   - D. Mengubah firewall Azure SQL menjadi Public 0.0.0.0/0

10. **Ketika sebuah semantic model gagal melakukan *Query Folding* pada sumber data relasional besar saat Import Mode, apa yang akan dilakukan oleh Mashup Engine pada host gateway?**
    - A. Membatalkan refresh secara otomatis dalam 5 detik.
    - B. Mengambil seluruh baris data mentah dari database ke host gateway dan mengeksekusi filter/agregasi di CPU dan disk lokal gateway.
    - C. Menerjemahkan rumus M menjadi stored procedure secara otomatis di database.
    - D. Mengonversi query menjadi format GraphQL.

---

#### Bagian C: Skenario Kasus Produksi (Analisis Arsitektur)

11. **Skenario Kasus 1: Failure Saat Failover Cluster Gateway**
    Sebuah kluster gateway terdiri dari 2 node: Node-A dan Node-B. Selama ini Node-A bertindak sebagai node utama dan menangani seluruh DirectQuery report eksekutif. Ketika Node-A sengaja dimatikan untuk OS security patching, traffic beralih ke Node-B. Namun, 100% pengguna DirectQuery yang menggunakan database SAP HANA menerima pesan error:
    `"Cannot connect to the SAP HANA server: The driver does not exist or failed to load."`
    Dataset berbasis SQL Server di cluster yang sama tetap berjalan normal di Node-B.
    *Pertanyaan:* Apa akar masalah teknis dari arsitektur tersebut, dan bagaimana prosedur preventif sebelum melakukan patch failover?

12. **Skenario Kasus 2: Bottleneck Memory Spooling pada Host Gateway**
    Sebuah host gateway 8-core, 32 GB RAM mengalami kegagalan refresh berkala pada jam 02:00 pagi saat 10 model semantik besar dieksekusi bersamaan. Administrator menemukan bahwa drive `C:\` memiliki sisa ruang kurang dari 200 MB saat insiden terjadi, namun kembali normal ke 50 GB setelah service di-restart atau refresh dibatalkan.
    *Pertanyaan:* Jelaskan mekanisme engine internal yang menyebabkan anomali konsumsi disk tersebut, parameter XML gateway apa yang harus disesuaikan, dan langkah remedi fisik apa yang harus diambil pada server?

13. **Skenario Kasus 3: Kegagalan Otomasi Pipeline CI/CD Service Principal**
    Tim Platform Data menyusun pipeline Azure DevOps untuk memindahkan model semantik dari workspace Dev ke workspace Prod. Pipeline berjalan menggunakan Service Principal. Saat mengeksekusi endpoint REST API:
    `POST https://api.powerbi.com/v1.0/myorg/groups/{prod_workspace_id}/datasets/{dataset_id}/Default.BindToGateway`
    Server mengembalikan kode status HTTP `403 Forbidden` dengan pesan JSON:
    `"Operation returned an invalid status code 'Forbidden'. Details: The user does not have administrative rights on the gateway cluster."`
    Padahal Service Principal tersebut telah ditetapkan sebagai **Admin** pada Workspace Prod target.
    *Pertanyaan:* Mengapa error tersebut terjadi meskipun Service Principal adalah Admin Workspace, dan konfigurasi eksplisit apa yang wajib ditambahkan di level Gateway Infrastructure?

---

### Kunci Jawaban Quiz

#### Bagian A & B
1. **C** (Port 5671 & 5672 adalah port standar untuk protokol AMQP/AMQPS yang digunakan Azure Service Bus).
2. **B** (`Microsoft.PowerBI.DataMovement.Pipeline.GatewayCore.dll.config` mengatur parameter runtime internal gateway).
3. **B** (Gateway bertindak sebagai polling client via persistent outbound sockets ke Azure Relay).
4. **C** (`Microsoft.Mashup.Container.NetFX45.exe` bertindak sebagai container komputasi isolasi M).
5. **B** (Recovery key digunakan untuk menghasilkan pasangan kunci asimetris dekripsi data credentials dan menambahkan node ke cluster).
6. **B - Salah** (Jika load balancing diaktifkan, Power BI Gateway Service menggunakan algoritma pembobotan metrik CPU dan penggunaan memori tiap node).
7. **A** (Azure AD UPN harus dipetakan secara identik atau melalui mapping rules ke On-Premises Active Directory UPN).
8. **B** (Tanpa batasan working set, single container dapat memakan seluruh memori fisik host hingga OS mengalami freeze).
9. **C** (VNet Data Gateway adalah solusi PaaS tanpa VM IaaS untuk sumber data internal Azure Virtual Network).
10. **B** (Mashup engine terpaksa mengeksekusi transformasi di memori/disk gateway jika query folding gagal).

#### Bagian C (Analisis Skenario Kasus Produksi)
11. **Analisis Skenario 1:**
    - *Akar Masalah:* Ketidakkonsistenan instalasi driver level-OS antar node. Driver 64-bit SAP HANA ODBC/Client terinstal pada Node-A tetapi belum terinstal atau memiliki versi/bitness yang berbeda pada Node-B.
    - *Prosedur Preventif:* Standarisasi Image Server Gateway (misal via Packer/Ansible). Pastikan setiap driver data source (Oracle ODAC, SAP GUI/HANA Client, dll.) diinstal secara identik pada seluruh node anggota cluster sebelum node digabungkan ke cluster produksi.
12. **Analisis Skenario 2:**
    - *Mekanisme:* Ketika transformasi M tidak fold ke source atau volume data ekstraksi melampaui RAM threshold (`MashupMemoryThresholdPercentage`), Mashup Container melakukan *memory swapping/spooling* sementara ke direktori OS `%TEMP%` di drive `C:\`. Akumulasi dari 10 dataset simultan memenuhi partisi disk OS.
    - *Remediasi Teknis:*
      1. Pindahkan lokasi penampungan spooling dengan mengatur environment variable sistem `TEMP`/`TMP` ke dedicated physical NVMe data drive terpisah (misal drive `D:\`).
      2. Set batas konsumsi per container via `MashupWorkingSetLimitMB` (misal 3072 MB).
      3. Batasi paralelisme container via `MashupDefaultPoolContainerMaxCount`.
      4. Jadwalkan ulang model semantik agar tidak dieksekusi pada jendela waktu yang sama persis (staggered refresh scheduling).
13. **Analisis Skenario 3:**
    - *Akar Masalah:* Role RBAC pada Power BI Workspace dan Gateway Clusters terpisah secara granular. Memiliki role *Admin* di level Workspace **tidak memberikan hak secara otomatis** untuk mengikat model ke suatu Gateway Cluster.
    - *Solusi:* Service Principal (melalui Object ID atau Client ID aplikasi) harus didaftarkan secara eksplisit sebagai **User** atau **Admin** pada Gateway Cluster target di level *Manage Gateways* (`api.powerbi.com/v1.0/myorg/gateways/{gateway_id}/users`), dengan permission `Read` atau `ReadWrite` terhadap datasource yang bersangkutan.

---

### 16. Summary

Implementasi arsitektur On-Premises Data Gateway tingkat enterprise bukan sekadar menginstal aplikasi agent pada sebuah VM, melainkan merancang integrasi hibrida yang tangguh (*resilient*), aman (*secure*), dan terukur (*scalable*):

1. **Topologi Tanpa Inbound:** Mengandalkan komunikasi outbound berbasis *Azure Service Bus Relay* (port TCP 443/5671) yang menjamin integritas firewall internal perusahaan tetap utuh tanpa membuka port masuk publik.
2. **Skalabilitas Multi-Node:** Membangun *High Availability Gateway Cluster* dengan opsi pembagian beban kueri (*Load Balancing*) mengeliminasi Single Point of Failure (SPOF) dan mengamankan throughput DirectQuery berkemampuan konkurensi tinggi.
3. **Isolasi Mesin Mashup:** Mengendalikan parameter `Microsoft.PowerBI.DataMovement.Pipeline.GatewayCore.dll.config` (`MashupWorkingSetLimitMB`, `MashupDefaultPoolContainerMaxCount`) sangat esensial guna mencegah fenomena *Out-Of-Memory* (OOM) dan *Disk Spooling Exhaustion* di drive sistem operasi.
4. **Governansi Modern Berbasis API:** Memisahkan hak kelola workspace dan infrastruktur gateway, serta mengeksekusi integrasi deployment pipeline menggunakan Entra ID Service Principal melalui Power BI REST API, menjamin konsistensi arsitektur tanpa intervensi manual manusia.