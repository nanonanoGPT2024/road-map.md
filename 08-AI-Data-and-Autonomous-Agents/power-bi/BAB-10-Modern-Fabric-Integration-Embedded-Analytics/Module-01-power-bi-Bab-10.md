# Bab 10: Modern Fabric Integration & Embedded Analytics — Module 01

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Mengimplementasikan Arsitektur Direct Lake:** Mengonfigurasi integrasi semantic model Power BI dengan Delta Tables di Microsoft Fabric OneLake tanpa melalui proses refresh konvensional (Import) maupun latensi query eksternal (DirectQuery).
- **Membangun Pipeline Embedded Analytics Skala Enterprise:** Merancang arsitektur analitik embedded berbasis pola *App-Owns-Data* menggunakan Microsoft Entra ID (dahulu Azure AD), Service Principal, dan Power BI REST API v2.
- **Mengorkestrasi Multi-Tenant Security & Dynamic RLS:** Mengimplementasikan Row-Level Security (RLS) dan Object-Level Security (OLS) secara dinamis menggunakan parameter `EffectiveIdentity` pada proses pembuatan *Embed Token*.
- **Mengelola State dan Lifecycle Embed Token:** Menerapkan strategi pertukaran token asinkron, penanganan rotasi token otomatis, mitigasi rate-limiting, dan transisi sesi pengguna tanpa diskoneksi render visual.
- **Mendeteksi dan Memitigasi Direct Lake Fallback:** Mengidentifikasi skenario fallback memori dari Direct Lake ke DirectQuery melalui log diagnosa Fabric SQL Analytics Endpoint dan XMLA endpoint telemetry.

---

## 2. Concept Overview

Integrasi antara Microsoft Fabric dan Power BI Embedded menandai transisi penting dari arsitektur analitik terfragmentasi ke arsitektur penyimpanan unifikasi berbasis *OneLake* dan konsumsi terdistribusi.

```
+-------------------------------------------------------------------------+
|                              MICROSOFT FABRIC                           |
|  +-------------------------------------------------------------------+  |
|  |                            OneLake                                |  |
|  |  [Delta Parquet Table] <--- V-Order Optimized Storage Engine     |  |
|  +-------------------------------------------------------------------+  |
|                                    |                                    |
|                                    v                                    |
|  +-------------------------------------------------------------------+  |
|  |                 Direct Lake Engine (VertiPaq Memory)             |  |
|  |   - No Data Ingestion/Refresh       - Direct Columnar Paging      |  |
|  |   - Zero-Copy Transcode             - Native Parquet Access       |  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
                                     |
                                     | (Metadata & DAX)
                                     v
+-------------------------------------------------------------------------+
|                          POWER BI EMBEDDED ENGINE                       |
|  +-------------------------------------------------------------------+  |
|  |                       Service Principal (SPN)                     |  |
|  |   - Client Credentials Grant        - Scoped Workspace Access    |  |
|  +-------------------------------------------------------------------+  |
|                                    |                                    |
|                                    v                                    |
|  +-------------------------------------------------------------------+  |
|  |                 GenerateTokenRequestV2 (REST API)                 |  |
|  |   - Dynamic RLS (Identities)        - Target Dataset Binding      |  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
                                     |
                                     | (HTTPS Embed Token)
                                     v
+-------------------------------------------------------------------------+
|                         APPLICATION FRONTEND                            |
|    PowerBI-JavaScript Client SDK ---> IFrame Hardware Accelerated Canvas|
+-------------------------------------------------------------------------+
```

### Mental Model: Paradigma Direct Lake vs Import vs DirectQuery
Secara historis, Power BI menawarkan dua mode utama:
1. **Import Mode:** Data dikompresi dan dimuat ke dalam memori VertiPaq. Kecepatan kueri tinggi, namun membutuhkan waktu *scheduled refresh* dan duplikasi data dari *source* ke Power BI Capacity.
2. **DirectQuery Mode:** Data tidak diduplikasi; DAX diterjemahkan menjadi kueri native sumber data (misal: T-SQL) saat runtime. Menjamin data riil, namun performanya lambat dan membebani sistem sumber transaksi.

**Direct Lake** menghilangkan trade-off ini. Tabel-tabel disimpan dalam format Parquet bersertifikasi Delta Lake di OneLake dengan optimasi *V-Order*. Mesin VertiPaq tidak mengimpor data melalui proses kompresi proprietary, melainkan *memetakan secara langsung* file Delta Parquet ke dalam struktur internal VertiPaq. Hasilnya: performa setara Import Mode tanpa memakan waktu data refresh dan tanpa beban translasi kueri DirectQuery.

### Embedded Analytics: App-Owns-Data vs. User-Owns-Data
- **User-Owns-Data:** Setiap pengguna akhir aplikasi harus memiliki lisensi Power BI Pro/PPU dan sesi Microsoft 365 aktif. Autentikasi dilakukan via OAuth 2.0 Authorization Code Flow delegasi langsung.
- **App-Owns-Data (Fokus Modul):** Dirancang untuk skenario SaaS multi-tenant. Pengguna aplikasi tidak memerlukan akun Azure/Power BI. Aplikasi mengotentikasi dirinya sendiri menggunakan kredensial Service Principal (SPN), mengasumsikan izin akses ke Fabric/Power BI Workspace, lalu menghasilkan *Embed Token* dengan kontrol izin terenkapsulasi secara terprogram.

---

## 3. Why It Matters

Di tingkat enterprise, pemisahan lapisan data storage dan visualization sering memicu fragmentasi tata kelola data:
1. **Data Gravity and Duplication:** Ketika dataset analitik mencapai puluhan terabyte, pipeline ETL yang menyalin data dari data lakehouse ke dataset Power BI Import konvensional memicu lonjakan biaya storage, kompleksitas idempotensi pipeline, dan latensi analitik (SLA data berjam-jam).
2. **Biaya Lisensi Skala Besar:** Membeli lisensi Power BI Pro untuk ratusan ribu pengguna eksternal aplikasi SaaS tidak feasible secara finansial. Pola *App-Owns-Data* berbasis Fabric Capacity (F SKU) atau Power BI Embedded (A SKU) memungkinkan skalabilitas berbasis konsumsi komputasi, bukan per-user licensing.
3. **Multi-Tenancy Security Leakage:** Skenario B2B SaaS menuntut isolasi data absolut. Implementasi RLS yang salah dalam kode aplikasi dapat mengekspos data antar-tenant. Pola token terpusat dengan `GenerateTokenRequestV2` memastikan isolasi data ditegakkan di level engine data melalui identitas runtime kriptografis.

---

## 4. Arsitektur & Diagram Komponen

Alur autentikasi, otorisasi, dan rendering embedded analytics terdistribusi:

```
[End User Browser]          [Backend App Service]         [Microsoft Entra ID]       [Power BI / Fabric API]
       |                              |                            |                           |
       | 1. HTTP GET /analytics/embed |                            |                           |
       |----------------------------->|                            |                           |
       |                              | 2. OAuth2 Client Creds     |                           |
       |                              |    (Tenant, ClientID, Sec) |                           |
       |                              |--------------------------->|                           |
       |                              | 3. Access Token (AAD)      |                           |
       |                              |<---------------------------|                           |
       |                              |                                                        |
       |                              | 4. POST /v1.0/myorg/GenerateToken                      |
       |                              |    (Payload: ReportId, DatasetId, Dynamic RLS Identity)|
       |                              |------------------------------------------------------->|
       |                              | 5. Embed Token JWT + Embed URL                         |
       |                              |<-------------------------------------------------------|
       | 6. Return Config JSON        |                                                        |
       |    {token, embedUrl, expiry} |                                                        |
       |<-----------------------------|                                                        |
       |                                                                                       |
       | 7. powerbi.embed(domElement, config)                                                  |
       |-------------------------------------------------------------------------------------->|
       | 8. Render Visuals Direct Lake (HTTP GET Delta Parquet from OneLake)                   |
       |<=====================================================================================>|
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Direct Lake Internal Execution & Framing
Direct Lake beroperasi melalui mekanisme memory-mapping:
1. **Metadata Loading:** Saat Semantic Model diakses, engine memuat skema dan metadata Delta Lake dari folder `_delta_log`.
2. **Column Paging on-demand:** Ketika kueri DAX dieksekusi, VertiPaq tidak membaca seluruh file Parquet. Ia hanya membaca *footer* metadata kolom yang dibutuhkan, mengalokasikan memori virtual, dan memetakan vektor kolom Parquet langsung ke struktur kolom vertikal VertiPaq.
3. **V-Order Optimization:** V-Order adalah algoritma penyusunan data tingkat penyimpanan Microsoft yang melakukan sorting, dictionary encoding, dan kompresi bit-packing pada file Parquet agar kompatibel 1:1 dengan struktur memori in-memory VertiPaq.
4. **Fallback Mechanism:** Direct Lake memiliki ambang batas memori (ditentukan oleh SKU Fabric, misalnya F64 = 64 Capacity Units). Jika:
   - Volume data melebihi alokasi memori SKU,
   - Terdapat operasi yang tidak didukung (misal: RLS kompleks tertentu atau dynamic M parameters),
   
   engine Direct Lake akan melakukan *fallback* otomatis ke mode **DirectQuery**. Hal ini menyebabkan penurunan performa signifikan karena query diarahkan kembali ke SQL Analytics Endpoint Lakehouse.

### 5.2 Dynamic Row-Level Security (RLS) via Embed Token
Pada model konvensional, RLS menggunakan fungsi DAX `USERNAME()` atau `USERPRINCIPALNAME()`. Dalam model *App-Owns-Data*, Service Principal bertindak sebagai master identity. Oleh karena itu, kita harus memasukkan identitas runtime secara eksplisit ke dalam *Embed Token Payload*:
- **Target Dataset:** Dataset/Semantic Model tempat RLS didefinisikan.
- **Roles:** Role DAX yang telah dibuat (misal: `TenantSecurityRole`).
- **Effective Identity String:** Nilai unik (misal: `tenant_id` atau `user_id`) yang dikirim dari Backend API ke Power BI API. Nilai ini akan menggantikan output fungsi `CUSTOMDATA()` atau `USERNAME()` dalam evaluasi aturan DAX.

### 5.3 Embed Token Expiry Lifecycle
Embed Token yang dihasilkan Power BI REST API memiliki masa aktif default **60 menit**. 
Aplikasi front-end harus mengimplementasikan interceptor asinkron untuk:
1. Menghitung sisa masa aktif token.
2. Memanggil endpoint backend untuk men-generate token baru 5-10 menit sebelum kedaluwarsa.
3. Menyuntikkan token baru ke instance Power BI JavaScript SDK menggunakan metode `report.setAccessToken(newToken)` tanpa melakukan refresh ulang DOM IFrame.

---

## 6. Production-Ready Code Implementation

Berikut implementasi backend production-ready menggunakan **Python (FastAPI)** dengan arsitektur modular, penanganan error ketat, validasi Pydantic, dan komunikasi REST API terenkapsulasi, diikuti implementasi client-side **TypeScript**.

### 6.1 Backend API Service (Python / FastAPI)

```python
# app/services/pbi_embed_service.py
from datetime import datetime, timezone
from typing import List, Optional
import httpx
from msal import ConfidentialClientApplication
from pydantic import BaseModel, Field


class EmbedConfigResponse(BaseModel):
    report_id: str
    embed_url: str
    embed_token: str
    token_id: str
    expiration: datetime


class RlsIdentity(BaseModel):
    username: str = Field(..., description="Unique Tenant ID or User Identifier")
    roles: List[str] = Field(..., min_items=1, description="Assigned DAX RLS roles")
    dataset_id: str = Field(..., description="Target Semantic Model ID")


class PowerBIEmbedManager:
    POWER_BI_SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]
    PBI_API_BASE_URL = "https://api.powerbi.com/v1.0/myorg"

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        workspace_id: str,
    ):
        self.workspace_id = workspace_id
        self._msal_app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
        )

    def _get_aad_token(self) -> str:
        """Mengambil token otentikasi Azure AD (App-Only) menggunakan client credentials grant."""
        result = self._msal_app.acquire_token_for_client(scopes=self.POWER_BI_SCOPE)
        if "access_token" in result:
            return result["access_token"]
        
        error_description = result.get("error_description", "Unknown MSAL error")
        raise PermissionError(f"Gagal mengotentikasi Service Principal: {error_description}")

    async def generate_embedded_report_config(
        self,
        report_id: str,
        target_dataset_id: str,
        identity: Optional[RlsIdentity] = None,
    ) -> EmbedConfigResponse:
        """
        Menghasilkan konfigurasi Embed Token V2 dengan Dynamic RLS.
        """
        aad_token = self._get_aad_token()
        headers = {
            "Authorization": f"Bearer {aad_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Mengambil Report Details untuk URL Embed
            report_url = f"{self.PBI_API_BASE_URL}/groups/{self.workspace_id}/reports/{report_id}"
            report_resp = await client.get(report_url, headers=headers)
            
            if report_resp.status_code != 200:
                raise ValueError(
                    f"Gagal mengambil metadata laporan [{report_resp.status_code}]: {report_resp.text}"
                )
            
            report_data = report_resp.json()
            embed_url = report_data.get("embedUrl")

            # 2. Membentuk payload GenerateTokenRequestV2
            token_request_payload = {
                "reports": [{"id": report_id, "allowEdit": False}],
                "datasets": [{"id": target_dataset_id}],
                "targetWorkspaces": [{"id": self.workspace_id}],
            }

            if identity:
                token_request_payload["identities"] = [
                    {
                        "username": identity.username,
                        "roles": identity.roles,
                        "datasets": [identity.dataset_id],
                    }
                ]

            # 3. Request Generate Token V2
            generate_token_url = f"{self.PBI_API_BASE_URL}/GenerateToken"
            token_resp = await client.post(
                generate_token_url, headers=headers, json=token_request_payload
            )

            if token_resp.status_code != 200:
                raise RuntimeError(
                    f"Gagal generate Embed Token [{token_resp.status_code}]: {token_resp.text}"
                )

            token_data = token_resp.json()

            # Normalisasi ISO 8601 parsing untuk expiration time
            expiration_str = token_data["expiration"].replace("Z", "+00:00")
            expiration_dt = datetime.fromisoformat(expiration_str)

            return EmbedConfigResponse(
                report_id=report_id,
                embed_url=embed_url,
                embed_token=token_data["token"],
                token_id=token_data["tokenId"],
                expiration=expiration_dt,
            )
```

```python
# app/main.py
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic_settings import BaseSettings
from app.services.pbi_embed_service import PowerBIEmbedManager, EmbedConfigResponse, RlsIdentity

class Settings(BaseSettings):
    AZURE_TENANT_ID: str
    AZURE_CLIENT_ID: str
    AZURE_CLIENT_SECRET: str
    FABRIC_WORKSPACE_ID: str
    
    class Config:
        env_file = ".env"

settings = Settings()
app = FastAPI(title="Fabric Analytics Embedding Service", version="1.0.0")

def get_pbi_manager() -> PowerBIEmbedManager:
    return PowerBIEmbedManager(
        tenant_id=settings.AZURE_TENANT_ID,
        client_id=settings.AZURE_CLIENT_ID,
        client_secret=settings.AZURE_CLIENT_SECRET,
        workspace_id=settings.FABRIC_WORKSPACE_ID,
    )

@app.get(
    "/api/v1/analytics/reports/{report_id}/token",
    response_model=EmbedConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def get_report_embed_token(
    report_id: str,
    dataset_id: str,
    tenant_key: str,  # Contoh implementasi: Tenant didapatkan dari session/token header
    pbi_manager: PowerBIEmbedManager = Depends(get_pbi_manager),
):
    try:
        # Enforce Row-Level Security identity secara deterministik
        identity = RlsIdentity(
            username=tenant_key,
            roles=["TenantPartitionRole"],
            dataset_id=dataset_id,
        )
        
        config = await pbi_manager.generate_embedded_report_config(
            report_id=report_id,
            target_dataset_id=dataset_id,
            identity=identity,
        )
        return config
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
```

### 6.2 Frontend Embedding & Lifecycle Handler (TypeScript)

Instalasi dependency client:
```bash
npm install powerbi-client
```

```typescript
// src/analytics/embedManager.ts
import * as pbi from 'powerbi-client';

export interface EmbedConfig {
  reportId: string;
  embedUrl: string;
  embedToken: string;
  expiration: string;
}

export class PowerBIEmbedController {
  private pbiService: pbi.service.Service;
  private currentReport: pbi.Report | null = null;
  private tokenRefreshTimer: number | null = null;
  private readonly datasetId: string;
  private readonly reportId: string;

  constructor(reportId: string, datasetId: string) {
    this.reportId = reportId;
    this.datasetId = datasetId;
    this.pbiService = new pbi.service.Service(
      pbi.factories.hpmFactory,
      pbi.factories.wpmpFactory,
      pbi.factories.routerFactory
    );
  }

  private async fetchEmbedConfig(): Promise<EmbedConfig> {
    const response = await fetch(
      `/api/v1/analytics/reports/${this.reportId}/token?dataset_id=${this.datasetId}`,
      { credentials: 'same-origin' }
    );
    if (!response.ok) {
      throw new Error(`Gagal mengambil config token: ${response.statusText}`);
    }
    return response.json();
  }

  public async renderReport(container: HTMLElement): Promise<void> {
    const configData = await this.fetchEmbedConfig();

    const config: pbi.models.IReportEmbedConfiguration = {
      type: 'report',
      id: configData.reportId,
      embedUrl: configData.embedUrl,
      accessToken: configData.embedToken,
      tokenType: pbi.models.TokenType.Embed,
      settings: {
        panes: {
          filters: { expanded: false, visible: false },
          pageNavigation: { visible: true, position: pbi.models.PageNavigationPosition.Left },
        },
        background: pbi.models.BackgroundType.Transparent,
      },
    };

    // Bersihkan embed yang sudah ada pada container jika ada
    this.pbiService.reset(container);

    this.currentReport = this.pbiService.embed(container, config) as pbi.Report;

    this.currentReport.on('loaded', () => {
      console.info('Direct Lake report metadata loaded successfully.');
    });

    this.currentReport.on('rendered', () => {
      console.info('Report canvas fully rendered.');
    });

    this.currentReport.on('error', (event) => {
      console.error('PBI SDK Error Context:', event.detail);
    });

    this.scheduleTokenRefresh(configData.expiration);
  }

  private scheduleTokenRefresh(expirationIso: string): void {
    if (this.tokenRefreshTimer) {
      window.clearTimeout(this.tokenRefreshTimer);
    }

    const expiryTime = new Date(expirationIso).getTime();
    const currentTime = Date.now();
    const safetyBufferMs = 10 * 60 * 1000; // Refresh 10 menit sebelum expired
    const timeoutDuration = expiryTime - currentTime - safetyBufferMs;

    this.tokenRefreshTimer = window.setTimeout(async () => {
      try {
        console.warn('Embed Token mendekati limit expired. Memulai background refresh...');
        const refreshedConfig = await this.fetchEmbedConfig();
        if (this.currentReport) {
          await this.currentReport.setAccessToken(refreshedConfig.embedToken);
          console.info('Access Token berhasil diperbarui tanpa reload IFrame.');
          this.scheduleTokenRefresh(refreshedConfig.expiration);
        }
      } catch (err) {
        console.error('Fatal: Gagal merefresh Embed Token secara berkala', err);
      }
    }, Math.max(timeoutDuration, 0));
  }

  public teardown(container: HTMLElement): void {
    if (this.tokenRefreshTimer) {
      window.clearTimeout(this.tokenRefreshTimer);
    }
    this.pbiService.reset(container);
    this.currentReport = null;
  }
}
```

---

## 7. Edge Cases & Failure Modes

### 7.1 Direct Lake Fallback ke DirectQuery (Silent Degradation)
- **Gejala:** Query latency meningkat drastis dari <100ms menjadi >5-10 detik.
- **Penyebab:** 
  1. Ukuran file Delta Parquet melebihi limit memori SKU Fabric capacity (OOM).
  2. Adanya unsupported DAX syntax (misal penggunaan referensi ke tabel/kolom yang memiliki variasi collation tidak kompatibel).
  3. Skema Delta Lake mengalami perubahan (*drift*) tanpa melakukan reload metadata pada semantic model.
- **Deteksi:** Pantau DMV via SQL Analytics Endpoint:
  ```sql
  SELECT * FROM sys.dm_exec_requests WHERE command LIKE '%Direct Lake%';
  ```
- **Solusi/Mitigasi:** Konfigurasi properti `DirectLakeBehavior` pada semantic model melalui Tabular Editor / TOM (Tabular Object Model) ke nilai `DirectLakeOnly`. Jika fallback terjadi, engine akan melemparkan exception eksplisit alih-alih menurunkan performa secara diam-diam (*fail-fast approach*).

### 7.2 Capacity Throttling & HTTP 429
- **Gejala:** Pemanggilan endpoint API `GenerateToken` mengembalikan respon `429 Too Many Requests` atau visualisasi mengembalikan kode error `PowerBIEntityNotFound / CapacityExceeded`.
- **Penyebab:** Fabric Capacity mengalami *interactive delay* atau *throttling* akibat penggunaan komputasi melebihi *Capacity Units* (CU) yang dibeli dalam sliding window 24 jam.
- **Mitigasi:**
  1. Terapkan strategi Exponential Backoff dengan Jitter pada API gateway.
  2. Implementasikan token caching di server side: Token yang sama dapat dibagikan kepada beberapa pengguna dari tenant yang sama selama identitas RLS yang disematkan identik, hingga 80% dari batas kedaluwarsa token tercapai.

### 7.3 Token Expiry Disconnection
- **Gejala:** IFrame menampilkan visual error: "Your session has expired" setelah 60 menit.
- **Penyebab:** Frontend SDK tidak mengeksekusi `setAccessToken()` secara asinkron sebelum TTL habis.
- **Solusi:** Lihat implementasi timer rekursif di Section 6.2 dengan safety buffer minimal 10 menit.

---

## 8. Trade-offs & Alternatif Solusi

| Dimensi | Direct Lake (Fabric) | Import Mode (VertiPaq) | DirectQuery Mode |
| :--- | :--- | :--- | :--- |
| **Data Freshness** | Riil (Sesuai commit Delta log OneLake) | Bergantung schedule refresh (misal: per 30 menit) | Real-time langsung ke sumber data |
| **Query Performance** | Sangat Tinggi (In-Memory Columnar Speed) | Sangat Tinggi (In-Memory Columnar Speed) | Rendah hingga Sedang (Tergantung database source) |
| **Beban Komputasi Storage**| Rendah (Zero-copy, menggunakan file Lakehouse) | Tinggi (Duplikasi data ke internal PBI format) | Tinggi pada Source DB (Kueri SQL berulang) |
| **Kebutuhan Lisensi/SKU** | Fabric Capacity (F2 ke atas) | Pro, PPU, atau Capacity | Pro, PPU, atau Capacity |
| **Dukungan Kompleksitas RLS**| Terbatas (Hanya single table/basic security filter) | Sangat Luas (Bisa complex DAX pattern) | Sedang (Dibatasi keterjemahan SQL native) |

### Keputusan Arsitektur: Service Principal vs Master User
- **Master User (OAuth User Impersonation):** *Deprecated*. Mengharuskan penyimpanan password di file konfigurasi, tidak mendukung MFA enterprise, dan rentan terhadap pemblokiran conditional access policy.
- **Service Principal (Entra ID App):** *Industry Standard*. Skalabel, rotasi rahasia menggunakan Azure Key Vault atau Managed Identity, dan sepenuhnya didukung oleh API v2 `GenerateTokenRequestV2`.

---

## 9. Best Practices & Standard Industri

1. **V-Order Maintenance:** Pastikan semua pipeline ingestion Spark atau Notebook di Fabric menjalankan write stream/batch dengan properti V-Order aktif:
   ```python
   spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
   df.write.format("delta").mode("append").save("Tables/fct_sales")
   ```
2. **Prinsip Least Privilege SPN:** Jangan berikan role Fabric *Admin* kepada Service Principal pada workspace. Tetapkan Service Principal hanya sebagai *Viewer* atau *Contributor* workspace, lalu aktifkan switch `Allow service principals to use Power BI APIs` di Fabric Admin Portal hanya untuk security groups tertentu.
3. **Workspace Isolation Pattern:** Untuk arsitektur strictly-regulated (Healthcare/Fintech), gunakan **One Workspace Per Tenant**. Untuk SaaS analitik umum, gunakan pola **Shared Workspace with Dynamic RLS** untuk menghemat batas alokasi kuota workspace fabric.
4. **Framing & Semantic Model Syncing:** Ketika Delta Lake di OneLake diperbarui via Lakehouse job, picu penyegaran metadata frame melalui REST API:
   ```bash
   POST https://api.powerbi.com/v1.0/myorg/groups/{workspaceId}/datasets/{datasetId}/refreshes
   Payload: { "type": "calculate" } # Sinkronisasi metadata frame tanpa reload storage
   ```

---

## 10. Hands-on Lab Exercise

### Skenario:
Anda bertugas membangun endpoint embedding SaaS untuk memvisualisasikan data penjualan multitenant yang tersimpan dalam format Delta Lake di Fabric OneLake menggunakan Dynamic RLS.

### Panduan Langkah Demi Langkah:

#### Langkah 1: Persiapan Delta Table di Microsoft Fabric
1. Buka Microsoft Fabric Workspace Anda, buat **Lakehouse** baru bernama `SalesLakehouse`.
2. Buka Notebook di Fabric, jalankan script PySpark berikut untuk menulis data bervolume mini dengan V-Order:
   ```python
   data = [
       ("Tenant_A", "Electronics", 15000.0, "2024-01-01"),
       ("Tenant_A", "Apparel", 450.0, "2024-01-02"),
       ("Tenant_B", "Groceries", 230.0, "2024-01-01"),
       ("Tenant_B", "Home", 1200.0, "2024-01-03"),
   ]
   columns = ["TenantId", "Category", "Amount", "Date"]
   df = spark.createDataFrame(data, columns)

   df.write.format("delta").mode("overwrite").saveAsTable("FactSales")
   ```

#### Langkah 2: Pembuatan Direct Lake Semantic Model
1. Masuk ke item `SalesLakehouse` di Fabric.
2. Klik **New semantic model** pada pita atas.
3. Beri nama `SalesDirectLakeModel`, pilih tabel `FactSales`.
4. Buka Semantic Model yang baru dibuat, masuk ke tab **Manage Roles**:
   - Buat Role baru: `TenantPartitionRole`.
   - Pada tabel `FactSales`, tambahkan ekspresi DAX RLS:
     ```dax
     [TenantId] = USERNAME()
     ```
   - Simpan perubahan.

#### Langkah 3: Registrasi Service Principal & Pemberian Akses
1. Daftarkan App Registration baru di portal Azure Entra ID: Beri nama `PowerBI-Embedded-App`. Catat `TenantId`, `ClientId`, dan buat `Client Secret`.
2. Buat Microsoft 365 Security Group (misal: `Fabric-Embedding-SecGroup`), masukkan SPN ke dalam group ini.
3. Di Admin Portal Fabric/Power BI: Aktifkan `Allow service principals to use Power BI APIs` dan masukkan security group tersebut.
4. Masuk ke Workspace Fabric tempat semantic model berada: Klik **Manage Access**, tambahkan Service Principal dengan role **Viewer**.

#### Langkah 4: Setup Backend API (Konfigurasi `.env`)
1. Buat folder project baru:
   ```bash
   mkdir pbi-embedded-lab && cd pbi-embedded-lab
   python -m venv venv
   source venv/bin/activate # Atau venv\Scripts\activate di Windows
   pip install fastapi uvicorn httpx msal pydantic pydantic-settings
   ```
2. Buat file `.env`:
   ```ini
   AZURE_TENANT_ID="<your-entra-tenant-id>"
   AZURE_CLIENT_ID="<your-spn-client-id>"
   AZURE_CLIENT_SECRET="<your-spn-client-secret>"
   FABRIC_WORKSPACE_ID="<your-fabric-workspace-id>"
   ```
3. Gunakan kode dari **Section 6.1** untuk membuat server FastAPI.
4. Jalankan backend:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

#### Langkah 5: Pengujian Endpoint
Jalankan perintah cURL untuk memvalidasi token generation dengan RLS untuk `Tenant_A`:
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/analytics/reports/<YOUR_REPORT_ID>/token?dataset_id=<YOUR_DATASET_ID>&tenant_key=Tenant_A"
```

Pastikan respons mengembalikan HTTP 200 dengan payload:
```json
{
  "report_id": "<your-report-id>",
  "embed_url": "https://app.powerbi.com/reportEmbed?...",
  "embed_token": "H4sIAAAAAAAE...",
  "token_id": "...",
  "expiration": "2024-..."
}
```

Ketika payload ini disuntikkan ke frontend controller (Section 6.2), visualisasi hanya akan merender baris milik `Tenant_A`, menegakkan prinsip isolasi data multi-tenant end-to-end tanpa memerlukan runtime SQL query translation overhead.