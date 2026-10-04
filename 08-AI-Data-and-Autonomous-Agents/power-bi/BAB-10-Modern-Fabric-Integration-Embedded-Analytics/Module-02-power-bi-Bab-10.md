# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi Power BI Embedded & Fabric OneLake

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengonstruksi arsitektur *Power BI Embedded* pola *App-Owns-Data* (Service-to-Service) menggunakan Azure Entra ID Service Principal, Custom API Gateway, dan Client-Side SDK secara aman dan *stateless*.
- Mengimplementasikan *Dynamic Row-Level Security (RLS)* dan multi-tenancy token impersonation menggunakan REST API `GenerateTokenRequestV2` dengan *effective identity* kustom.
- Mengintegrasikan Microsoft Fabric OneLake dan Delta Lake tables ke dalam Power BI Semantic Model menggunakan engine Direct Lake tanpa proses refresh terjadwal (zero-copy query routing).
- Mengonfigurasi otomatisasi provisioning, CI/CD deployment pipeline, dan capacity scaling (Azure A-SKU / Fabric F-SKU) menggunakan Terraform, PowerShell Fabric REST API, dan Azure DevOps/GitHub Actions.
- Mengoptimalkan throughput, latensi rendering embed, *query memory footprint*, serta mengatasi *cold start* visual report pada aplikasi enterprise skala jutaan pengguna.

---

## 2. Prerequisite

Sebelum memulai modul ini, Anda wajib memiliki pemahaman mendalam dan akses terhadap:
- **Identitas & Keamanan**: Azure Entra ID (sebelumnya Azure AD), konfigurasi App Registrations, Client Secrets/Certificates, API Permissions (`Dataset.Read.All`, `Report.Read.All` via delegated/application scope), dan Service Principal profiles.
- **Bahasa Pemrograman**: Node.js/TypeScript (v18+ LTS) atau C# (.NET 8 LTS), serta ES6+ JavaScript untuk manipulasi DOM pada sisi client.
- **Engine Data & Pemodelan**: DAX (*Data Analysis Expressions*), DirectQuery vs. Import Mode vs. Direct Lake architecture, serta partisi Apache Parquet di OneLake.
- **Infrastruktur & Cloud**: Azure Subscription aktif dengan hak akses minimal `Contributor` untuk deployment Fabric Capacity (F SKU) atau Power BI Embedded Capacity (A SKU), dan instalasi CLI (`az cli`, `fabric-cli`).

---

## 3. Concept & Internal Architecture (Mendalam)

Implementasi Power BI Embedded di skala enterprise didorong oleh pemisahan antara control plane, data plane, dan security perimeter. 

```
+-------------------------------------------------------------------------------------------------------------------------+
|                                                   ENTERPRISE HYBRID CLOUD                                              |
|                                                                                                                         |
|  +--------------------+               +-----------------------------+               +--------------------------------+  |
|  |   Client Browser   | <===========> |    Corporate API Gateway    | <===========> | Azure Entra ID (Token Issuing) |  |
|  |  (powerbi-client)  |  Session/JWT  | (Node.js / .NET Core 8 App) |  OBO / Client | (STS Service Engine)           |  |
|  +--------------------+               +-----------------------------+   Credentials +--------------------------------+  |
|          ^                                           |                                              |                   |
|          | (Embed Config + Embed Token)              |                                              |                   |
|          v                                           v                                              v                   |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  |                                            POWER BI / FABRIC SAAS LAYER                                           |  |
|  |                                                                                                                   |  |
|  |  +---------------------+        Token Validation       +--------------------+      Metadata      +-------------+  |  |
|  |  | Fabric Direct Lake  | <---------------------------  | Workspace Engine   | <----------------- | Capacity    |  |  |
|  |  | Engine (VertiPaq)   |                               | (Power BI REST API)|                    | Resource    |  |  |
|  |  +---------------------+                               +--------------------+                    | Scheduler   |  |  |
|  |             |                                                     |                              | (F/A-SKU)   |  |  |
|  |             v (Parquet Metadata Vectorization)                    v                              +-------------+  |  |
|  |  +---------------------------------------------------------------------------------------------+                  |  |
|  |  | Fabric OneLake Delta Lake Tables (Direct Framing over V-Order Parquet Files)                |                  |  |
|  |  +---------------------------------------------------------------------------------------------+                  |  |
|  +-------------------------------------------------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------------------------------------------------+
```

### 3.1. App-Owns-Data vs. User-Owns-Data Architecture
Pada model enterprise modern, arsitektur aplikasi backend yang mengonsumsi analitik terbagi menjadi dua paradigma:

1. **User-Owns-Data (Embed for your organization)**:
   - Pengguna akhir harus memiliki akun Azure Entra ID organisasional dan lisensi Power BI Pro / PPU (Premium Per User).
   - Autentikasi menggunakan OAuth 2.0 Authorization Code Grant Flow with PKCE.
   - Hak akses data dan visual langsung mewarisi policy workspace Power BI.

2. **App-Owns-Data (Embed for your customers)**:
   - Pengguna aplikasi adalah entitas eksternal atau sistem multi-tenant yang tidak memiliki lisensi Power BI atau akun Entra ID.
   - Backend aplikasi bertindak sebagai *master authority* menggunakan **Service Principal (SPN)**.
   - SPN meminta Azure AD Token, lalu menukarnya ke Power BI Token Service untuk menghasilkan runtime scoped **Embed Token** (`GenerateTokenRequestV2`).
   - Keamanan data multi-tenant ditentukan secara dinamis via RLS parameter injection di level backend runtime.

### 3.2. Direct Lake vs. DirectQuery vs. Import Mode
Direct Lake adalah inovasi arsitektur di Microsoft Fabric yang merevolusi analitik embedded berskala masif:
- **Import Mode**: Data di-*cache* ke dalam VertiPaq engine di memori capacity. Kecepatan query sangat tinggi (sub-detik), tetapi membutuhkan refresh terjadwal dan dibatasi ukuran file dataset maksimal.
- **DirectQuery**: Data tidak diduplikasi; DAX diterjemahkan menjadi T-SQL/native query saat runtime. Tidak ada limit data, tetapi latensi query tinggi, rentan *bottleneck* konkurensi database sumber, dan banyak fungsi DAX tidak didukung.
- **Direct Lake**: Mengeliminasi translasi query dan pergerakan data. VertiPaq engine membaca file Parquet langsung dari OneLake storage. Metadata delta log dipetakan langsung ke struktur kolom vertikal VertiPaq di memori saat dibutuhkan (*paging on-demand*). Hasilnya: kecepatan query setara Import Mode, tanpa perlu pipeline ETL refresh terpisah, dan mendukung dataset berukuran multi-terabyte.

### 3.3. Token Lifecycle & The Token V2 Subsystem
Embed Token yang dihasilkan oleh `GenerateTokenRequestV2` adalah JWT berumur pendek (default: 60 menit) yang ditandatangani secara kriptografis oleh Power BI Token Authority. Token ini memuat:
- Deklarasi izin report (`view`, `edit`, `create`).
- Target dataset dan target report ID.
- Identitas RLS (`EffectiveIdentity`), mencakup `username`, `roles`, dan custom `customData` payload.
- Lifetime boundaries: Aplikasi wajib mengimplementasikan pola refresh asinkronus (`setAccessToken`) di sisi client sebelum token kedaluwarsa tanpa me-reload iframe report.

---

## 4. Why & What

| Fitur / Pola | Mengapa Diperlukan di Enterprise? | Apa yang Terjadi Jika Salah Desain? |
| :--- | :--- | :--- |
| **Service Principal Authentication** | Menghilangkan ketergantungan pada akun master user personal (*single point of failure*, bypass MFA, rotasi password berkala). | Pipeline otomatisasi putus saat password kedaluwarsa; security audit gagal karena melanggar prinsip non-repudiation. |
| **GenerateTokenV2 (Multi-Resource)** | Mengizinkan satu embed token mengakses banyak report, dataset lintas workspace, dan dashboard sekaligus. | Terjadi *token storming*; latensi aplikasi membengkak akibat request token terpisah untuk setiap komponen visual dashboard. |
| **Dynamic RLS via `customData`** | Menyederhanakan penulisan aturan filter DAX ke dalam satu fungsi terpusat (`CUSTOMDATA()`), menghindari pembuatan ratusan role terpisah. | *Role sprawl* (ratusan role statis); pemeliharaan model menjadi rapuh (*unmaintainable*); overhead memori semantic model meningkat drastis. |
| **Fabric Direct Lake Framing** | Memotong waktu latensi data dari jam/menit menjadi detik tanpa beban komputasi ganda (ETL ke semantic model). | Jika fallback ke DirectQuery terjadi tanpa disadari, latensi visual melonjak dari 400ms menjadi 15+ detik di level konkurensi tinggi. |
| **Phased Embedding & Visual Preloading** | Memisahkan fase inisialisasi iframe (`powerbi.preload`), konfigurasi metadata, dan proses render UI visual. | White-screen latency tinggi (>4-7 detik) saat transisi halaman aplikasi, menurunkan User Experience (UX) secara drastis. |

---

## 5. How (Workflow Detail)

### 5.1. Alur Runtime Embed Token Generation & Client Injection
Berikut adalah alur eksekusi dari inisiasi user sampai report berhasil ter-render secara interaktif:

```
[End User Browser]          [Enterprise API Gateway]         [Azure Entra ID]       [Power BI REST Service]
        |                              |                             |                         |
        |--- 1. GET /api/reports/1 --->|                             |                         |
        |    (Auth Bearer App JWT)     |--- 2. OAuth2 Client Creds ->|                         |
        |                              |    (Client ID & Secret)     |                         |
        |                              |<-- 3. App Access Token -----|                         |
        |                              |                                                       |
        |                              |--- 4. POST /v1.0/myorg/GenerateToken (V2 Payload) --->|
        |                              |       (DatasetID, ReportID, Dynamic RLS, CustomData)  |
        |                              |<-- 5. Return Embed Token (Scoped JWT) ----------------|
        |                              |                                                       |
        |<-- 6. Return Payload JSON ---|                                                       |
        |    {embedToken, embedUrl, id}|                                                       |
        |                              |                                                       |
        |=== 7. powerbi.embed(domElement, config) ============================================>|
        |       (Mengirim Embed Token langsung via IFrame PostMessage API)                      |
        |<== 8. Render Visuals & Establish Direct Lake Query Channel ===========================|
```

### 5.2. Direct Lake Fallback Mechanics & Mitigasi
Jika kapasitas memori Fabric (F-SKU) terlampaui atau terjadi modifikasi schema di Delta Table yang belum disinkronkan, engine Power BI akan melakukan **Silent Fallback** ke DirectQuery.
1. Evaluasi kapasitas memori: Query memeriksa apakah ukuran kolom Delta Parquet melampaui limit RAM SKU.
2. Sinkronisasi metadata: Jika delta log versi tabel OneLake lebih baru daripada snapshot semantic model, engine memicu fallback otomatis.
3. Mitigasi: Ubah properti Semantic Model `DirectLakeBehavior` dari `Automatic` menjadi `DirectLakeOnly`. Jika memori tidak cukup atau metadata desinkron, sistem akan melempar error eksplisit sehingga tim SRE dapat memicu auto-scale atau eksekusi refresh metadata alih-alih membiarkan user mengalami penurunan performa ekstrem.

---

## 6. Analogy & Diagram ASCII

### Analogi: Kartu Akses Hotel Mewah (Keycard) vs. Kunci Fisik

* **Pola Klasik (Import / DirectQuery Biasa)**: Seperti gudang arsip manual. Setiap kali pengunjung meminta laporan, petugas harus menyalin lembaran dari gudang besar ke etalase toko (Import), atau petugas harus bolak-balik berlari ke gudang pusat untuk setiap pertanyaan kecil pengunjung (DirectQuery).
* **Fabric Direct Lake**: Toko dan gudang menyatu menggunakan dinding kaca tembus pandang berteknologi tinggi. Data tersimpan dalam kontainer standar (Delta Parquet di OneLake). Mesin VertiPaq membaca langsung kontainer tersebut tanpa memindahkannya, seperti sistem pemindaian barcode berkecepatan cahaya.
* **Embed Token V2 & Dynamic RLS**: Seperti kartu kunci elektronik hotel (RFID Keycard). Backend Anda adalah resepsionis hotel tepercaya. Saat tamu (End User) check-in, resepsionis tidak memberikan master key gedung (Service Principal Secret), melainkan memprogram kartu kunci sementara (Embed Token) yang hanya bisa membuka Pintu Kamar 402 (RLS Tenant ID = 402) dan hanya berlaku selama 60 menit.

```
       CONCURRENT CLIENT REQUESTS
   +---------------------------------+
   | Tenant A | Tenant B | Tenant C  |
   +----------+----------+----------+
        |          |          |
        +----------+----------+
                   |
                   v
    +-----------------------------+
    |   Enterprise API Gateway    |  ===> Mengesahkan Token Aplikasi
    +-----------------------------+
                   |
    Enkapsulasi RLS: customData = Tenant_ID
                   |
                   v
    +-----------------------------+
    |  Power BI Embedded Engine   |
    |  (Fabric Capacity F64)      |
    +-----------------------------+
                   |
       [ DIRECT LAKE ENGINE ]
                   |
         Zero-Copy In-Memory Paging
                   |
                   v
    +-----------------------------+
    |    Microsoft OneLake        |
    |  (Tables / V-Order Parquet) |
    | +-------------------------+ |
    | | Tenant A | B | C Data   | |
    | +-------------------------+ |
    +-----------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Inisialisasi Embed Client Sederhana (Vanilla JS)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Power BI Embedded Minimal</title>
  <script src="https://cdn.jsdelivr.net/npm/powerbi-client@2.22.3/dist/powerbi.min.js"></script>
  <style>
    #reportContainer { width: 100%; height: 600px; border: 1px solid #ccc; }
  </style>
</head>
<body>
  <div id="reportContainer"></div>
  <script>
    const models = window['powerbi-client'].models;
    const config = {
      type: 'report',
      tokenType: models.TokenType.Embed,
      accessToken: 'TOKEN_DARI_BACKEND',
      embedUrl: 'https://app.powerbi.com/reportEmbed?reportId=YOUR_REPORT_ID',
      id: 'YOUR_REPORT_ID',
      permissions: models.Permissions.View,
      settings: {
        filterPaneEnabled: false,
        navContentPaneEnabled: true
      }
    };
    const reportContainer = document.getElementById('reportContainer');
    const report = powerbi.embed(reportContainer, config);

    report.on("rendered", () => {
      console.log("Report berhasil di-render.");
    });
  </script>
</body>
</html>
```

---

### 7.2. Practical Example: Enterprise Node.js / TypeScript Embed Gateway Service

Implementasi backend production-grade untuk menangani integrasi Entra ID, eksekusi REST API V2 dengan Dynamic RLS berbasis `CustomData`, serta penanganan token caching.

#### Backend Controller (TypeScript)

```typescript
// src/services/PowerBiEmbedService.ts
import axios from 'axios';
import { ConfidentialClientApplication } from '@azure/msal-node';

interface EmbedConfigResponse {
  reportId: string;
  reportName: string;
  embedUrl: string;
  accessToken: string;
  expiry: string;
}

interface TenantContext {
  tenantId: string;
  userId: string;
  role: string;
}

export class PowerBiEmbedService {
  private msalClient: ConfidentialClientApplication;
  private readonly scope: string[] = ['https://analysis.windows.net/powerbi/api/.default'];
  private readonly powerBiApiRoot = 'https://api.powerbi.com/v1.0/myorg';

  constructor(
    private clientId: string,
    private clientSecret: string,
    private authorityUrl: string,
    private workspaceId: string
  ) {
    this.msalClient = new ConfidentialClientApplication({
      auth: {
        clientId: this.clientId,
        authority: this.authorityUrl,
        clientSecret: this.clientSecret,
      },
    });
  }

  private async getAppAccessToken(): Promise<string> {
    const authResult = await this.msalClient.acquireTokenByClientCredential({
      scopes: this.scope,
    });
    if (!authResult || !authResult.accessToken) {
      throw new Error('Gagal mendapatkan Azure Entra ID token untuk Service Principal.');
    }
    return authResult.accessToken;
  }

  public async getReportEmbedDetails(
    reportId: string,
    datasetId: string,
    tenantContext: TenantContext
  ): Promise<EmbedConfigResponse> {
    const aadToken = await this.getAppAccessToken();

    // 1. Ambil Report Metadata
    const reportUrl = `${this.powerBiApiRoot}/groups/${this.workspaceId}/reports/${reportId}`;
    const reportMetadataRes = await axios.get(reportUrl, {
      headers: { Authorization: `Bearer ${aadToken}` },
    });
    const { name: reportName, embedUrl } = reportMetadataRes.data;

    // 2. Siapkan Token V2 Payload dengan Dynamic RLS
    // Effective identity disesuaikan dengan skema multi-tenant menggunakan CUSTOMDATA()
    const tokenRequestBody = {
      reports: [{ id: reportId }],
      datasets: [{ id: datasetId }],
      targetWorkspaces: [{ id: this.workspaceId }],
      identities: [
        {
          username: tenantContext.userId,
          roles: ['MultiTenantDynamicRole'],
          customData: JSON.stringify({
            tenantId: tenantContext.tenantId,
            accessLevel: tenantContext.role,
          }),
          datasets: [datasetId],
        },
      ],
    };

    // 3. Request Embed Token V2
    const tokenEndpoint = `${this.powerBiApiRoot}/GenerateToken`;
    const tokenRes = await axios.post(tokenEndpoint, tokenRequestBody, {
      headers: {
        Authorization: `Bearer ${aadToken}`,
        'Content-Type': 'application/json',
      },
    });

    return {
      reportId,
      reportName,
      embedUrl,
      accessToken: tokenRes.data.token,
      expiry: tokenRes.data.expiration,
    };
  }
}
```

#### Client-side SDK Wrapper (TypeScript Modern)

```typescript
// src/client/EmbedManager.ts
import * as pbi from 'powerbi-client';

export class EmbedManager {
  private powerBiService: pbi.service.Service;
  private currentReport: pbi.Report | null = null;
  private tokenRefreshTimeout: number | null = null;

  constructor() {
    this.powerBiService = new pbi.service.Service(
      pbi.factories.hpmFactory,
      pbi.factories.wpmpFactory,
      pbi.factories.routerFactory
    );
  }

  public bootstrap(container: HTMLElement): void {
    // Pre-create iframe untuk memotong waktu rendering
    this.powerBiService.bootstrap(container, { type: 'report' });
  }

  public embedReport(
    container: HTMLElement,
    reportId: string,
    embedUrl: string,
    token: string,
    expiryUtc: string
  ): pbi.Report {
    const config: pbi.models.IReportEmbedConfiguration = {
      type: 'report',
      id: reportId,
      embedUrl: embedUrl,
      accessToken: token,
      tokenType: pbi.models.TokenType.Embed,
      permissions: pbi.models.Permissions.View,
      settings: {
        panes: {
          filters: { expanded: false, visible: false },
          pageNavigation: { visible: true, position: pbi.models.PageNavigationPosition.Left },
        },
        background: pbi.models.BackgroundType.Transparent,
      },
    };

    this.currentReport = this.powerBiService.embed(container, config) as pbi.Report;

    this.currentReport.on('loaded', () => {
      console.info(`[PowerBI-Embed] Report ID: ${reportId} successfully loaded.`);
    });

    this.currentReport.on('rendered', () => {
      console.info(`[PowerBI-Embed] Visual elements rendering finalized.`);
    });

    this.currentReport.on('error', (event) => {
      console.error('[PowerBI-Embed] Internal Error:', event.detail);
    });

    this.setupAutoTokenRefresh(expiryUtc, reportId);

    return this.currentReport;
  }

  private setupAutoTokenRefresh(expiryUtc: string, reportId: string): void {
    if (this.tokenRefreshTimeout) {
      window.clearTimeout(this.tokenRefreshTimeout);
    }

    const expiryTime = new Date(expiryUtc).getTime();
    const currentTime = Date.now();
    // Jadwalkan refresh token 10 menit sebelum waktu kedaluwarsa
    const refreshLeadTime = 10 * 60 * 1000;
    const timeUntilRefresh = Math.max(0, expiryTime - currentTime - refreshLeadTime);

    this.tokenRefreshTimeout = window.setTimeout(async () => {
      try {
        console.warn('[PowerBI-Embed] Refreshing Embed Token...');
        const response = await fetch(`/api/reports/${reportId}/refresh-token`);
        const { accessToken, expiry } = await response.json();

        if (this.currentReport) {
          await this.currentReport.setAccessToken(accessToken);
          console.info('[PowerBI-Embed] Embed Token updated smoothly.');
          this.setupAutoTokenRefresh(expiry, reportId);
        }
      } catch (err) {
        console.error('[PowerBI-Embed] Critical failure refreshing Embed Token', err);
      }
    }, timeUntilRefresh);
  }
}
```

#### Dynamic RLS DAX Implementation
Ekspresi DAX yang di-inject pada semantic model untuk mengevaluasi parameter JSON dari backend:

```dax
// Table Security Filter pada tabel: Dim_Tenant
[Tenant_ID] = 
VAR RawJson = CUSTOMDATA()
VAR CurrentTenant = PATHITEM(SUBSTITUTE(SUBSTITUTE(RawJson, "{""tenantId"":""", ""), """}", ""), 1)
RETURN
    IF(
        ISBLANK(CurrentTenant),
        FALSE(),
        Dim_Tenant[Tenant_UID] = CurrentTenant
    )
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Global FinTech Core Banking Analytics Hub
* **Skala Sistem**: 120.000 entitas *merchant*, 450 juta transaksi bulanan, konkurensi puncak 2.500 *analytics requests/second*.
* **Tantangan Arsitektur**:
  - Pelaporan transaksi real-time (*near zero-latency data fresh rate*).
  - Waktu muat embed visual awal (initial load) sebelumnya mencapai 8,4 detik pada model DirectQuery biasa.
  - Skala tenancy sangat luas; tidak mungkin membuat 120.000 workspace atau report terpisah.
  - Ancaman *data leakage* antar nasabah/merchant sangat sensitif terhadap audit compliance FinTech internasional.

### Arsitektur Solusi Terpasang
1. **Fabric OneLake & Direct Lake Pipeline**:
   - Ingest transaksi core banking via Kafka Connect ke Azure Data Lake Storage Gen2 / Fabric OneLake dalam format Apache Parquet.
   - Algoritma V-Order diaktifkan untuk optimasi sorting Parquet columnar buffer.
   - Semantic Model dibangun di atas OneLake menggunakan engine Direct Lake dengan properti `DirectLakeBehavior = DirectLakeOnly` (menolak translasi query SQL lambat).
2. **Dynamic Multi-Tenancy Engine**:
   - Satu Master Report & Dataset deployed ke Fabric Workspace berkapasitas **F64**.
   - API Gateway perusahaan mengenkapsulasi JWT kustom; backend mengonversi token login merchant menjadi `CustomData: {"tenantId": "M-99882", "allowedOrgs": [10, 12, 14]}`.
3. **Phased Loading & Client Bootstrap**:
   - Halaman portal memanggil `powerbi.bootstrap()` saat pengguna baru masuk ke halaman dashboard induk sebelum navigasi ke tab analitik.
   - Layout disesuaikan agar query visual pertama hanya memuat aggregasi ringkasan (KPI Cards) sebelum memuat matriks transaksi detail.

### Hasil Metrik Produksi

```
+-----------------------------------+--------------------+--------------------+---------------+
| Metrik Evaluasi                   | DirectQuery Lama   | Modern Direct Lake | Peningkatan   |
+-----------------------------------+--------------------+--------------------+---------------+
| P95 Initial Visual Render Latency | 8.400 ms           | 780 ms             | 10.7x Faster  |
| Data Freshness SLA                | 60 menit (Batch)   | < 5 detik          | 720x Realtime |
| Database Source Compute Load      | 92% CPU Peak       | < 5% CPU           | 94% Offload   |
| Incident Cross-Tenant Leakage     | 0 insiden          | 0 insiden          | 100% Compliant|
+-----------------------------------+--------------------+--------------------+---------------+
```

---

## 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                    +------------------------------------+
                    |        Direct Lake Engine          |
                    | (Low Latency, High Cloud RAM Cost) |
                    +------------------------------------+
                                      /\
                                     /  \
                                    /    \
                                   /      \
                                  /        \
                                 /          \
+----------------------------------+      +----------------------------------+
|           Import Mode            | <==> |        DirectQuery Mode          |
| (High Perf, Low Storage Cost,    |      | (Zero ETL, Max Scale Storage,    |
|  Stale Data via Refresh Batch)   |      |  High Latency, High Source Load) |
+----------------------------------+      +----------------------------------+
```

### Matriks Komparasi Karakteristik Operasional

| Dimensi | Import Mode | DirectQuery Mode | Fabric Direct Lake |
| :--- | :--- | :--- | :--- |
| **Query Latency (P50)** | Ultra Low (< 300ms) | High (1.500ms - 15.000ms) | Ultra Low (< 400ms) |
| **Data Freshness** | Bergantung schedule refresh (min. 30 menit) | Real-time langsung dari underlying DB | Near Real-time (sesuai landing parquet Delta) |
| **Beban Memory Capacity** | Sangat Tinggi (Data duplicate di VertiPaq) | Sangat Rendah (VertiPaq hanya memproses DAX tree) | Tinggi (Metadata & delta column vector di-paging) |
| **Biaya Lisensi / Compute** | Rendah - Menengah (PPU / Power BI Pro / SKU kecil) | Menengah (Beban biaya dialihkan ke DB target) | Tinggi (Membutuhkan Fabric Capacity min. F64 untuk prod) |
| **Limitasi Fitur DAX** | Lengkap (Mendukung semua ekspresi DAX murni) | Terbatas (Fungsi tertentu ditolak/error) | Lengkap (Sama dengan Import Mode jika tidak fallback) |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal yang Sering Terjadi
1. **Direct Lake Silently Falling Back to DirectQuery**:
   - *Sebab*: Tabel Parquet memiliki tipe data unsupported (misal: `decimal` dengan precision > 38, `binary` string besar) atau alokasi memori melampaui SKU.
   - *Dampak*: Visual mendadak lambat tanpa throwing visual crash.
   - *Solusi*: Atur properti model `DirectLakeBehavior` ke `DirectLakeOnly` via XMLA Endpoint / Tabular Editor.
2. **Kompilasi String RLS JSON yang Salah (Malformed JSON Escape)**:
   - *Sebab*: Karakter kutip dua pada JSON string di `CustomData` tidak di-escape dengan benar di payload POST API.
   - *Dampak*: Error `400 Bad Request` dari Power BI REST API atau DAX `CUSTOMDATA()` me-resolve string kosong, menyebabkan blank report.
3. **Hardcoding Client Secret di Aplikasi Frontend**:
   - *Sebab*: Developer frontend mencoba meminta AAD token langsung dari browser untuk menghemat waktu integrasi backend.
   - *Dampak*: Pelanggaran keamanan tingkat kritis; Service Principal Secret bocor dan workspace berpotensi diambil alih penyerang.

### 10.2. Panduan Troubleshooting Terstruktur

```
Gejala Masalah: Visual Menampilkan "Can't load the data for this visual"
   |
   +---> Periksa status HTTP Network Call di Developer Tools
          |
          +-- (A) Error 403 Forbidden:
          |       - Verifikasi apakah Embed Token sudah expired (Cek timestamp exp JWT via jwt.ms).
          |       - Verifikasi apakah Service Principal dimasukkan ke dalam Admin/Member workspace.
          |       - Cek setting Tenant Admin Power BI: "Allow service principals to use Power BI APIs".
          |
          +-- (B) Error 401 Unauthorized:
          |       - AAD Access Token Service Principal invalid atau salah authority tenant ID.
          |
          +-- (C) Query Error / Visual Crash:
                  - Buka DAX Studio, koneksikan via XMLA Endpoint.
                  - Eksekusi query dengan menyuntikkan CustomData impersonation:
                    SET CUSTOMDATA = "{\"tenantId\":\"T-123\"}";
                  - Periksa jika ada syntax error atau division by zero pada aturan RLS.
```

---

## 11. Best Practices (Production Checklist)

### Security & Governance
- [ ] Nonaktifkan master-user flow; gunakan Entra ID Service Principal murni dengan rotasi certificate via Azure Key Vault.
- [ ] Batasi hak akses Service Principal di tenant setting menggunakan Security Group tertentu (jangan buka untuk seluruh organisasi).
- [ ] Set semantic model dataset ke enkripsi ganda (*Bring Your Own Key - BYOK*) jika diwajibkan oleh standar compliance (seperti HIPAA, PCI-DSS).

### Performance & Engine Direct Lake
- [ ] Aktifkan **V-Order** pada semua write operations Fabric Lakehouse/Warehouse untuk menyusun Parquet file secara optimal bagi VertiPaq reader.
- [ ] Atur `DirectLakeBehavior` = `DirectLakeOnly` untuk mendeteksi fallback failure sedini mungkin di testing environment.
- [ ] Minimalkan kardinalitas kolom (*high cardinality column pruning*): hapus timestamp detik/milidetik jika agregasi hanya butuh granularitas tanggal.

### Client-Side Embedding UX
- [ ] Gunakan pola `powerbi.bootstrap()` sebelum user mengeklik dashboard untuk menginisialisasi shell iframe di background.
- [ ] Implementasikan auto-refresh token asinkronus menggunakan event listener atau scheduled timer minimal 10 menit sebelum token TTL habis.
- [ ] Terapkan visual layout responsif (`LayoutType.Custom`) dan nonaktifkan elemen bawaan yang tidak diperlukan (misalnya default filter pane, visual header context menus).

---

## 12. Hands-on Practice

Simpan seluruh file implementasi di direktori: `hands-on/m02/`

### Step 1: Inisialisasi Project Gateway & Dependencies

```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install express dotenv axios @azure/msal-node cors
npm install --save-dev typescript @types/express @types/node @types/cors ts-node
npx tsc --init
```

### Step 2: Konfigurasi Environment Variable
Buat file `hands-on/m02/.env`:

```ini
PORT=3000
AZURE_TENANT_ID=00000000-0000-0000-0000-000000000000
POWERBI_CLIENT_ID=00000000-0000-0000-0000-000000000000
POWERBI_CLIENT_SECRET=your_spn_secret_value_here
POWERBI_WORKSPACE_ID=00000000-0000-0000-0000-000000000000
POWERBI_REPORT_ID=00000000-0000-0000-0000-000000000000
POWERBI_DATASET_ID=00000000-0000-0000-0000-000000000000
```

### Step 3: Implementasi Server Embed Token Gateway
Buat file `hands-on/m02/server.ts`:

```typescript
import express, { Request, Response } from 'express';
import dotenv from 'dotenv';
import cors from 'cors';
import axios from 'axios';
import { ConfidentialClientApplication } from '@azure/msal-node';

dotenv.config();

const app = express();
app.use(express.json());
app.use(cors());

const config = {
  tenantId: process.env.AZURE_TENANT_ID!,
  clientId: process.env.POWERBI_CLIENT_ID!,
  clientSecret: process.env.POWERBI_CLIENT_SECRET!,
  workspaceId: process.env.POWERBI_WORKSPACE_ID!,
  reportId: process.env.POWERBI_REPORT_ID!,
  datasetId: process.env.POWERBI_DATASET_ID!,
};

const msalClient = new ConfidentialClientApplication({
  auth: {
    clientId: config.clientId,
    authority: `https://login.microsoftonline.com/${config.tenantId}`,
    clientSecret: config.clientSecret,
  },
});

app.get('/api/embed-config', async (req: Request, res: Response) => {
  try {
    const tenantParam = (req.query.tenantId as string) || 'TENANT-DEFAULT';

    // 1. Dapatkan Token AAD via App-Only Flow
    const aadTokenRes = await msalClient.acquireTokenByClientCredential({
      scopes: ['https://analysis.windows.net/powerbi/api/.default'],
    });

    if (!aadTokenRes?.accessToken) {
      return res.status(500).json({ error: 'Auth failed with Entra ID' });
    }

    const headers = {
      Authorization: `Bearer ${aadTokenRes.accessToken}`,
      'Content-Type': 'application/json',
    };

    // 2. Ambil Metadata Report
    const reportData = await axios.get(
      `https://api.powerbi.com/v1.0/myorg/groups/${config.workspaceId}/reports/${config.reportId}`,
      { headers }
    );

    // 3. Request Embed Token V2 dengan RLS CustomData
    const v2Payload = {
      reports: [{ id: config.reportId }],
      datasets: [{ id: config.datasetId }],
      targetWorkspaces: [{ id: config.workspaceId }],
      identities: [
        {
          username: `user_${tenantParam}`,
          roles: ['AppDynamicRLS'],
          customData: tenantParam,
          datasets: [config.datasetId],
        },
      ],
    };

    const tokenRes = await axios.post(
      'https://api.powerbi.com/v1.0/myorg/GenerateToken',
      v2Payload,
      { headers }
    );

    return res.json({
      reportId: config.reportId,
      embedUrl: reportData.data.embedUrl,
      accessToken: tokenRes.data.token,
      expiration: tokenRes.data.expiration,
    });
  } catch (error: any) {
    console.error('Embed Gateway Error:', error.response?.data || error.message);
    return res.status(500).json({ error: 'Failed to generate embed token' });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`[Gateway] Power BI Token Service running on port ${PORT}`);
});
```

### Step 4: Implementasi Client Testbed Frontend
Buat file `hands-on/m02/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Production Embed Testbed</title>
  <script src="https://cdn.jsdelivr.net/npm/powerbi-client@2.22.3/dist/powerbi.min.js"></script>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 20px; }
    .controls { margin-bottom: 15px; }
    #reportHost { width: 100%; height: 750px; border: 1px solid #e1e4e8; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    .status-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; background: #eef; }
  </style>
</head>
<body>
  <h2>Enterprise Analytics Dashboard Testbed</h2>
  <div class="controls">
    <label for="tenantSelect">Select Simulated Tenant: </label>
    <select id="tenantSelect">
      <option value="TENANT-ACME-CORP">Acme Corp (ID: TENANT-ACME-CORP)</option>
      <option value="TENANT-STARK-IND">Stark Ind (ID: TENANT-STARK-IND)</option>
    </select>
    <button onclick="loadAnalytics()">Load Report</button>
    <span id="status" class="status-badge">Idle</span>
  </div>

  <div id="reportHost"></div>

  <script>
    const reportHost = document.getElementById('reportHost');
    const statusLabel = document.getElementById('status');
    let currentReport = null;

    async function loadAnalytics() {
      const tenant = document.getElementById('tenantSelect').value;
      statusLabel.innerText = "Requesting Scoped Token...";

      try {
        const response = await fetch(`http://localhost:3000/api/embed-config?tenantId=${tenant}`);
        const data = await response.json();

        if (data.error) throw new Error(data.error);

        statusLabel.innerText = "Rendering Report Engine...";

        const config = {
          type: 'report',
          tokenType: window['powerbi-client'].models.TokenType.Embed,
          accessToken: data.accessToken,
          embedUrl: data.embedUrl,
          id: data.reportId,
          settings: {
            panes: {
              filters: { visible: false },
              pageNavigation: { visible: true, position: 1 }
            }
          }
        };

        // Reset container
        powerbi.reset(reportHost);
        currentReport = powerbi.embed(reportHost, config);

        currentReport.on("rendered", () => {
          statusLabel.innerText = `Active Session: Render Complete (${tenant})`;
        });

      } catch (err) {
        console.error(err);
        statusLabel.innerText = "Error: " + err.message;
      }
    }
  </script>
</body>
</html>
```

---

## 13. Exercise

### Level Easy
Ubah konfigurasi embed settings di `hands-on/m02/index.html` untuk mematikan context menu visual (klik kanan mouse pada visual chart) agar user aplikasi tidak dapat melihat opsi "Show as a table" atau opsi export default Power BI.

### Level Medium
Perluas `hands-on/m02/server.ts` agar menerima parameter array `pages` opsional dari URL request, lalu gunakan Client SDK `report.setPage("TargetPageName")` setelah report memicu event `loaded` untuk memastikan navigasi langsung menuju halaman analitik yang diminta user.

### Level Hard
Implementasikan skema rotasi token asinkronus murni pada `hands-on/m02/index.html`. Daftarkan event listener yang membaca metadata header expiry dari backend gateway, dan secara otomatis memicu pemanggilan endpoint backend 5 menit sebelum token habis, lalu mengeksekusi `report.setAccessToken(newToken)` tanpa terjadi flickering atau refresh IFrame.

---

## 14. Challenge

Rancang arsitektur sistem **Disaster Recovery & Scale-out Multi-Region** untuk Power BI Embedded:
- Skenario: Anda memiliki data transaksi nasabah yang terbagi di 2 region (East US dan West Europe).
- Aturan Kebijakan: Data residensi mewajibkan user Eropa hanya membaca data dari Fabric OneLake West Europe, dan user Amerika dari East US. Namun, portal aplikasi web diakses secara global lewat Azure Front Door.
- **Tugas Arsitektur**:
  1. Gambarkan diagram urutan (sequence diagram) REST API provisioning token dinamis yang secara cerdas mendeteksi lokasi user lalu memetakan token ke Service Principal, Workspace, dan Fabric F-Capacity yang sesuai region secara transparan.
  2. Definisikan strategi failover: Jika Capacity F-SKU di West Europe mengalami outage / throttle 100% capacity consumption, bagaimana sistem backend memitigasi traffic tanpa memicu pelanggaran data residensi GDPR.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)

1. **Apa perbedaan mendasar antara model *User-Owns-Data* dan *App-Owns-Data*?**
   - A. Model User-Owns-Data tidak mendukung visual kustom.
   - B. Model App-Owns-Data menggunakan satu Service Principal untuk mengabstraksi lisensi Power BI dari pengguna akhir aplikasi.
   - C. Model User-Owns-Data hanya mendukung DirectQuery, sedangkan App-Owns-Data hanya mendukung Import.
   - D. Model App-Owns-Data mewajibkan setiap user akhir memiliki akun di Azure Active Directory.

2. **Kapan *Embed Token* kedaluwarsa secara default jika tidak dikonfigurasi secara eksplisit?**
   - A. 15 menit
   - B. 60 menit
   - C. 24 jam
   - D. Tidak pernah kedaluwarsa kecuali di-revoke

3. **Komponen SDK apa yang digunakan pada sisi browser untuk merender report?**
   - A. `@azure/identity`
   - B. `powerbi-client`
   - C. `powerbi-report-builder`
   - D. `fabric-lakehouse-sdk`

4. **Metode client-side apa yang digunakan untuk menginisialisasi shell IFrame di awal guna memangkas latensi rendering?**
   - A. `powerbi.preload()`
   - B. `powerbi.bootstrap()`
   - C. `powerbi.initShell()`
   - D. `powerbi.warmup()`

5. **Apa ekstensi dan format dasar penyimpanan data di OneLake yang memungkinkan engine Direct Lake membaca data secara native?**
   - A. CSV Terkompresi Gzip
   - B. JSON Lines
   - C. Apache Parquet berbasis Delta Lake
   - D. Proprietary ABF (.abf) Files

---

### Bagian 2: Intermediate (5 Soal)

6. **Mengapa pemanggilan fungsi DAX `CUSTOMDATA()` lebih diutamakan dibandingkan menulis aturan RLS dinamis menggunakan `USERPRINCIPALNAME()` pada skenario App-Owns-Data skala besar?**
   - A. Karena `USERPRINCIPALNAME()` memblokir eksekusi VertiPaq engine.
   - B. Karena `CUSTOMDATA()` memungkinkan backend aplikasi menyuntikkan metadata tenancy atau claims JSON secara langsung saat pembuatan Embed Token tanpa perlu memetakan ribuan email user ke Entra ID.
   - C. Karena `USERPRINCIPALNAME()` hanya berfungsi pada akun Office 365 Personal.
   - D. Karena `CUSTOMDATA()` mengenkripsi query menggunakan algoritma AES-256 secara native.

7. **Apa yang dimaksud dengan fenomena *Direct Lake Silent Fallback*?**
   - A. Direct Lake otomatis berpindah ke Import Mode setiap tengah malam.
   - B. Engine Power BI secara otomatis beralih mengeksekusi query melalui DirectQuery saat tabel melanggar batasan ukuran memori atau metadata OneLake tidak sinkron.
   - C. Laporan berpindah ke format PDF statis saat koneksi internet terputus.
   - D. REST API menolak request token dan mengalihkan trafik ke endpoint publik.

8. **Untuk mencegah terjadinya silent fallback pada semantic model Direct Lake, properti model apa yang harus diubah melalui endpoint XMLA?**
   - A. `DirectLakeBehavior` diubah dari `Automatic` menjadi `DirectLakeOnly`.
   - B. `DirectQueryMode` diatur ke `Strict`.
   - C. `EngineType` diatur ke `In-Memory-Lock`.
   - D. `AutoSyncDeltaLog` diatur ke `Disabled`.

9. **Jika backend Anda perlu menghasilkan satu Embed Token yang dapat membuka Report A di Workspace 1 dan Report B di Workspace 2 secara bersamaan, API endpoint mana yang harus dipanggil?**
   - A. `/v1.0/myorg/groups/{groupId}/reports/{reportId}/GenerateToken`
   - B. `/v1.0/myorg/GenerateToken` (GenerateTokenRequestV2)
   - C. `/v1.0/myorg/admin/tokens/batch`
   - D. `/v1.0/myorg/capacities/token`

10. **Bagaimana cara memperbarui masa berlaku Embed Token pada client aplikasi yang sedang aktif tanpa me-reload visual atau me-refresh halaman IFrame browser?**
    - A. Memanggil `powerbi.reset(container)` lalu panggil embed ulang.
    - B. Memanggil `report.setAccessToken(newToken)`.
    - C. Melakukan manipulasi DOM dengan mengganti atribut `src` pada elemen `iframe`.
    - D. Menghancurkan session via `report.reload()`.

---

### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario Kasus 1**:
    Sebuah aplikasi SaaS multi-tenant mengalami lonjakan request HTTP 429 (*Too Many Requests*) dari endpoint Power BI REST API `GenerateToken` saat jam sibuk pagi hari ketika ribuan pengguna serentak membuka dashboard. Setelah diaudit, backend Anda melakukan panggilan `GenerateToken` terpisah untuk setiap tab laporan yang dibuka oleh pengguna.
    *Arsitektur mitigasi apa yang paling tepat untuk mengeliminasi HTTP 429 tersebut tanpa menaikkan biaya capacity?*
    - A. Buat banyak Service Principal baru dan putar (*round-robin*) pemanggilannya.
    - B. Gabungkan permintaan token multi-report dalam satu payload panggilan `GenerateTokenRequestV2` multi-resource, serta implementasikan token caching di layer backend (Redis) dengan key berbasis User Session & Tenant Context selama token masih valid.
    - C. Migrasikan seluruh laporan dari Fabric F-SKU ke lisensi Power BI Shared Pro.
    - D. Kurangi resolusi grafik visual pada Power BI Desktop agar payload data lebih ringan.

12. **Skenario Kasus 2**:
    Tim Data Engineering memperbarui skema tabel Delta Lake di OneLake dengan menghapus satu kolom usang dan menambahkan kolom baru menggunakan Spark Notebook di Microsoft Fabric. Segera setelah job ETL selesai, pengguna aplikasi embedded melaporkan bahwa dashboard mereka menampilkan error: `Direct Lake query failed because table schema mismatch`.
    *Langkah orkestrasi apa yang terlewat dalam pipeline otomatisasi data engineering tersebut?*
    - A. Tidak me-restart instance Fabric Capacity.
    - B. Tidak mengeksekusi refresh metadata semantic model (`POST /datasets/{datasetId}/refreshes`) untuk menyinkronkan framing VertiPaq dengan Delta Lake log versi terbaru.
    - C. Tidak menghapus Service Principal dari Access Control List (ACL) OneLake.
    - D. Lupa mengubah ekstensi file dari `.parquet` ke `.csv`.

13. **Skenario Kasus 3**:
    Hasil load-testing menunjukkan latensi rendering visual pada embedded report meningkat secara signifikan ketika jumlah baris data transaksi mencapai 200 juta baris. Pemeriksaan menunjukkan bahwa aturan Dynamic RLS menggunakan kalkulasi string kompleks:
    `[Tenant_ID] = PATHITEM(SUBSTITUTE(CUSTOMDATA(), ":", "|"), 2)`.
    *Optimasi DAX dan data modeling apa yang harus diimplementasikan untuk mengembalikan performa ke sub-detik?*
    - A. Ganti string splitting dinamis runtime di DAX; ubah parsing dilakukan di layer ingest OneLake dengan materialisasi kolom ID terindeks integer murni, lalu sederhanakan filter RLS menjadi perbandingan integer langsung: `Dim_Merchant[TenantKey] = INT(CUSTOMDATA())`.
    - B. Gunakan fungsi `LOOKUPVALUE` di seluruh calculated columns model.
    - C. Pindahkan model dari Direct Lake kembali ke DirectQuery tradisional.
    - D. Matikan fitur RLS dan filter data langsung di level JavaScript Frontend menggunakan SDK `report.setFilters()`.

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B** — Model App-Owns-Data menggunakan identitas Service Principal untuk bertindak atas nama aplikasi, sehingga pengguna akhir tidak memerlukan lisensi individu Power BI.
2. **B** — Default Token Life Time untuk Embed Token yang dihasilkan via API adalah 60 menit.
3. **B** — Library resmi client-side untuk embedding Power BI adalah `powerbi-client`.
4. **B** — `powerbi.bootstrap()` digunakan untuk menginisialisasi IFrame sebelum konfigurasi dan token final disuntikkan.
5. **C** — Direct Lake membaca langsung data berformat Parquet dengan struktur Delta Lake di OneLake.

#### Bagian 2: Intermediate
6. **B** — `CUSTOMDATA()` sangat fleksibel karena menerima string arbitrary (misal: JSON payload) yang ditentukan backend saat runtime, memisahkan manajemen akses data dari struktur direktori Entra ID.
7. **B** — Silent fallback adalah mekanisme otomatis engine VertiPaq mengalihkan beban Direct Lake ke DirectQuery biasa ketika limitasi spesifikasi terlampaui.
8. **A** — `DirectLakeBehavior = DirectLakeOnly` memastikan sistem menolak eksekusi jika tidak bisa dijalankan secara Direct Lake murni, mencegah query lambat di background.
9. **B** — Endpoint global V2 (`/v1.0/myorg/GenerateToken`) memungkinkan batching multiple reports, datasets, dan workspaces dalam satu token terpadu.
10. **B** — `report.setAccessToken()` memperbarui token aktif secara mulus di IFrame tanpa mengganggu rendering visual yang sedang aktif.

#### Bagian 3: Skenario Kasus Produksi
11. **B** — Batching via Token V2 mengurangi jumlah call ke REST API, dan Redis token caching memastikan backend tidak meminta token baru ke Microsoft setiap kali user me-refresh halaman yang sama.
12. **B** — Direct Lake memerlukan sinkronisasi schema metadata antara Delta Transaction Log dan VertiPaq schema frame; ini diselesaikan via dataset refresh call (yang hanya menyinkronkan metadata, bukan menyalin data).
13. **A** — Operasi string manipulation kompleks pada aturan RLS di runtime mematahkan optimasi storage engine dictionary VertiPaq. Integer comparison langsung memaksimalkan kecepatan traversal VertiPaq index. Opsi D sangat salah karena memfilter via JavaScript client-side menimbulkan celah keamanan fatal (*security breach*).

---

## 16. Summary

Implementasi Power BI Embedded dan Fabric Integration skala enterprise menuntut pergeseran paradigma dari sekadar "menampilkan dashboard di web" menuju "arsitektur analitik terdistribusi performa tinggi". Pola **App-Owns-Data** berbasis **Service Principal** yang dikombinasikan dengan **GenerateTokenRequestV2** dan **Dynamic RLS (`CUSTOMDATA`)** menyediakan fondasi keamanan multi-tenant yang tangguh, aman, dan dapat diskalakan tanpa overhead lisensi per-pengguna.

Di layer data engine, **Fabric Direct Lake** menjembatani jurang pemisah antara kecepatan kilat *Import Mode* dan fleksibilitas volume besar *DirectQuery*. Dengan memanfaatkan zero-copy query langsung di atas file Delta Parquet di OneLake, enterprise dapat menghadirkan data analitik near-real-time tanpa latensi ETL tradisional. Keberhasilan implementasi produksi ditentukan oleh orkestrasi yang presisi: mitigasi fallback Direct Lake sedini mungkin, pengamanan siklus hidup token secara asinkronus di sisi client SDK, serta isolasi identitas data secara ketat di layer backend gateway.