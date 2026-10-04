# Bab 07: Enterprise Governance, Data Security & Compliance

## Modul 01: Enterprise Tenant Governance, End-to-End Security Architecture (RLS/OLS), dan Purview Information Protection

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mendesain dan Mengonfigurasi Tenant Architecture**: Mengelola *Tenant Settings* Power BI skala enterprise dengan prinsip *Least Privilege* menggunakan Microsoft Entra ID Security Groups.
- **Mengimplementasikan Dynamic Row-Level Security (RLS)**: Menulis ekspresi DAX performan tinggi berbasis `USERPRINCIPALNAME()` dengan optimasi relasi star-schema dan tabel pemetaan hak akses (security matrix).
- **Menerapkan Object-Level Security (OLS)**: Mengamankan metadata dan data pada tingkat tabel dan kolom sensitif (PII/Financial) menggunakan Tabular Model Scripting Language (TMSL) dan Tabular Object Model (TOM).
- **Mengintegrasikan Microsoft Purview Information Protection**: Mengonfigurasi *Sensitivity Labels* dengan enkripsi downstream otomatis untuk file ekspor (.xlsx, .pbix, .pdf).
- **Membangun Automated Compliance & Audit Engine**: Mengembangkan skrip otomatisasi berbasis Python dan Power BI REST API untuk mengekstraksi log audit, memantau *orphan workspaces*, dan memvalidasi kepatuhan tata kelola secara berkala.

---

### 2. Concept Overview

Tata kelola enterprise pada Power BI memisahkan antara **Control Plane** (pengaturan konfigurasi tenant, kapasitas, dan lisensi) dan **Data Plane** (akses dataset, query execution, pemodelan data, dan visualisasi).

```
                      +------------------------------------------+
                      |         Control Plane (Tenant Admin)     |
                      |  - Entra ID Groups & Conditional Access  |
                      |  - Microsoft Purview Information Labels  |
                      |  - Power BI Admin API & Activity Logs    |
                      +--------------------+---------------------+
                                           | Policy Enforcement
                                           v
+-----------------------------------------------------------------------------------+
|                        Data Plane (Workspace & Semantic Layer)                    |
|                                                                                   |
|   +-----------------------+     +-----------------------+                         |
|   |  Dataset / Data Model | --> | Row-Level Security    | DAX Filtering Logic     |
|   |  (Tabular Engine)     |     +-----------------------+                         |
|   |                       | --> | Object-Level Security | Metadata Masking (TMSL) |
|   +-----------------------+     +-----------------------+                         |
|               |                                                                   |
|               v                                                                   |
|   +-----------------------+                                                       |
|   | Downstream Artifacts  | Enforce Purview Encryption (.xlsx, .pbix, .pdf)       |
|   +-----------------------+                                                       |
+-----------------------------------------------------------------------------------+
```

#### Mental Model: Defense-in-Depth dalam Power BI
1. **Perimeter Layer**: Otentikasi berbasis Microsoft Entra ID (dahulu Azure AD) dengan *Conditional Access Policies* (MFA, IP whitelisting, compliant device verification).
2. **Tenant Layer**: Pembatasan fitur sensitif (ekspor data, publish to web, eksternal sharing) yang didelegasikan hanya ke grup keamanan tertentu.
3. **Workspace Layer**: Pengendalian akses berbasis peran (*Admin*, *Member*, *Contributor*, *Viewer*). Kontrol terhadap siapa yang bisa memodifikasi vs mengonsumsi data.
4. **Semantic Model Layer**:
   - **Row-Level Security (RLS)**: Membatasi baris data yang dapat dilihat oleh pengguna tertentu berdasarkan konteks identitas mereka. RLS tidak menyembunyikan skema, melainkan menyaring baris data (`WHERE` clause otomatis pada engine VertiPaq).
   - **Object-Level Security (OLS)**: Membatasi visibilitas objek skema (seluruh tabel atau kolom tertentu). Jika pengguna tidak memiliki izin, kolom tersebut dianggap tidak eksis secara struktural; query yang meminta kolom tersebut akan gagal atau mengembalikan error metadata.
5. **Data Protection Layer**: Enkripsi diam (*at-rest*) dengan Customer-Managed Keys (BYOK), enkripsi bergerak (*in-transit*) dengan TLS 1.3, dan proteksi berkas downstream dengan Microsoft Purview Sensitivity Labels.

---

### 3. Why It Matters

Tanpa arsitektur tata kelola yang terdefinisi dengan ketat, adopsi Power BI pada skala enterprise sering memicu krisis keamanan dan operasional:

- **Regulasi & Sanksi Hukum**: Kegagalan membatasi akses PII (Personally Identifiable Information) melanggar GDPR, HIPAA, dan UU Pelindungan Data Pribadi (UU PDP). Denda finansial dan sanksi operasional dapat dikenakan jika data gaji atau riwayat medis bocor antar departemen.
- **Data Exfiltration**: Fitur default seperti *Publish to Web* atau *Export to Excel* memungkinkan data rahasia internal terindeks oleh search engine publik atau disimpan di drive pribadi tanpa enkripsi.
- **Query Performance Degradation**: Pola dynamic RLS yang buruk (misalnya menggunakan fungsi DAX non-sargable atau filter dua arah yang kompleks) dapat mematikan performa Formula Engine (FE) VertiPaq, meningkatkan konsumsi CPU Capacity (Fabric/Premium), dan menyebabkan *throttling*.
- **Admin Blindspots**: Tanpa pemantauan audit log terprogram, administrator tidak dapat membuktikan kepatuhan audit historis (siapa yang mengakses dataset apa, kapan data diekspor, dan perubahan izin apa yang terjadi).

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut merepresentasikan alur komprehensif dari otentikasi identitas, evaluasi keamanan VertiPaq (RLS & OLS), hingga penegakan kebijakan ekspor downstream.

```
[ End User / Consumer ]
         |
         | 1. HTTPS Request + Entra ID Bearer Token (JWT)
         v
+-----------------------------------------------------------------------+
| Microsoft Entra ID                                                    |
| - Validasi Conditional Access (MFA, Device Compliance, IP Range)       |
| - Identifikasi UPN (User Principal Name) & Group Membership           |
+-----------------------------------------------------------------------+
         |
         | 2. Token Validated (Includes UPN & Object ID)
         v
+-----------------------------------------------------------------------+
| Power BI Service (Tenant / Premium Capacity)                          |
|                                                                       |
|  [ Workspace Security Gate ]                                          |
|  - Role: Viewer (Hanya role Viewer yang mengeksekusi RLS/OLS)         |
|  - Member/Contributor/Admin bypass RLS secara default (edit access)   |
|                               |                                       |
|                               v                                       |
|  [ Tabular Engine (VertiPaq) ]                                        |
|  +-----------------------------------------------------------------+  |
|  | Semantic Model                                                  |  |
|  |                                                                 |  |
|  |  +------------------------+      +---------------------------+  |  |
|  |  | Object-Level Security  | ---> | Unlicensed Column/Table?  |  |  |
|  |  | Enforcement (OLS)      |      | True -> Schema Error/Hide |  |  |
|  |  +------------------------+      +---------------------------+  |  |
|  |               |                                                 |  |
|  |               v Passed                                          |  |
|  |  +-----------------------------------------------------------+  |  |
|  |  | Dynamic Row-Level Security (RLS) Filter Engine            |  |  |
|  |  | DAX Evaluation:                                           |  |  |
|  |  | SecurityMatrix[Email] = USERPRINCIPALNAME()              |  |  |
|  |  | Filter context otomatis disuntikkan ke Data Model        |  |  |
|  |  +-----------------------------------------------------------+  |  |
|  |               |                                                 |  |
|  |               v Filtered Dataset                                |  |
|  |  +-----------------------------------------------------------+  |  |
|  |  | Storage Engine (SE) & Formula Engine (FE) Execution       |  |  |
|  |  +-----------------------------------------------------------+  |  |
|  +-----------------------------------------------------------------+  |
|                               |                                       |
|                               v                                       |
|  [ Downstream Egress Protection Engine ]                              |
|  - Microsoft Purview Information Protection (MIP) Labels Interceptor  |
|  - Label: "Confidential - Financial"                                  |
+-----------------------------------------------------------------------+
         |
         | 3. Render Dashboard / Export Event
         v
+-----------------------------------------------------------------------+
| Exported Artifacts (.xlsx, .pbix, .pdf)                               |
| - Header metadata disisipi cryptographic watermark                   |
| - Terenkripsi via Azure Rights Management Service (RMS)              |
| - Hanya akun terotorisasi yang dapat membuka file di desktop lokal    |
+-----------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### Dynamic Row-Level Security (RLS)
Secara teknis, RLS bekerja dengan menyuntikkan predikat logis ke dalam *Storage Engine* VertiPaq.
- **Sistem Tradisional**: Membuat satu peran statis per wilayah (misal: *Role_Asia*, *Role_Europe*). Ini tidak *scaleable* karena jika terdapat 100 wilayah, diperlukan 100 peran berbeda.
- **Dynamic RLS**: Menggunakan satu peran tunggal yang mengevaluasi identitas sesi pengguna menggunakan fungsi DAX `USERPRINCIPALNAME()` (atau `USERNAME()`). 
- **Pola Desain Relasi**:
  1. Tabel `DimUserAccess` berisi kolom `UserEmail` dan `AccessKey` (misal: `StoreKey` atau `DepartmentID`).
  2. Relasi dibuat antara `DimUserAccess` dan tabel dimensi bisnis (misal: `DimStore`) dengan arah filter *single* atau *bi-directional*.
  3. **Optimasi Kritis**: Relasi dua arah (*bidirectional cross-filtering*) pada tabel sekuriti dapat menyebabkan *ambiguous paths* dan *performance bottleneck*. Praktik terbaik enterprise adalah menjaga relasi satu arah (*single direction*) dan menggunakan fungsi DAX `LOOKUPVALUE` atau memanfaatkan pola *star-schema* murni dengan filter yang dialirkan dari dimensi sekuriti ke tabel fakta.

#### Object-Level Security (OLS)
Berbeda dengan RLS yang memfilter *data rows*, OLS mengontrol visibilitas *metadata*:
- OLS dikonfigurasi pada level model metadata via TMSL atau TOM (tidak bisa dibuat murni melalui UI Power BI Desktop biasa; membutuhkan alat seperti Tabular Editor).
- OLS mendukung dua tingkat proteksi:
  - `None`: Pengguna dalam peran tersebut sama sekali tidak dapat melihat metadata tabel/kolom. Kolom tersebut tidak muncul dalam *field list*, dan visual yang merujuk kolom tersebut akan menghasilkan pesan error: *"The visual has encountered an error: The field '...' does not exist"*.
  - `Read`: Default permission, pengguna dapat membaca metadata dan data.
- **Perhatian Penting**: Jika sebuah *Measure* merujuk ke kolom yang diproteksi oleh OLS (`None`), measure tersebut juga akan error secara runtime bagi pengguna tersebut. Oleh karena itu, measure dependen harus diproteksi dengan OLS yang setara.

#### Purview Information Protection Integration
- Integrasi ini menjembatani boundary antara SaaS (Power BI Service) dan OS lokal pengguna.
- Saat administrator mengaitkan label sensitivitas Microsoft 365 / Purview ke dataset, label tersebut diwariskan (*inherited*) ke laporan (*reports*), dasbor, dan aplikasi turunan.
- Ketika pengguna mengklik **Export to Excel**, Power BI API tidak sekadar menulis raw tabular byte. Service ini memanggil API Azure Rights Management Service (RMS), menyematkan label metadata yang terenkripsi, dan mengenkripsi payload berkas dengan kunci simetris yang dibungkus oleh sertifikat tenant. Hasilnya, berkas `.xlsx` yang diunduh tetap terproteksi meskipun ditransfer melalui flashdisk atau email eksternal.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi komprehensif sistem tata kelola dan keamanan:

#### A. DAX: Optimized Dynamic Security Model Implementation
Pola DAX berikut diimplementasikan pada Semantic Model di dalam Power BI Desktop / Tabular Editor.

```dax
/*
  Table: Security_UserAssignment
  Columns:
    - UserEmail (STRING) : email/UPN pengguna
    - OrgUnitKey (INTEGER) : foreign key ke DimOrganization
    - IsAdmin (BOOLEAN)   : bypass flag untuk audit internal
*/

-- Penerapan RLS Filter Expression pada tabel 'DimOrganization'
VAR CurrentUserEmail = USERPRINCIPALNAME()
VAR IsUserGlobalAdmin = 
    CALCULATE(
        MAX(Security_UserAssignment[IsAdmin]),
        Security_UserAssignment[UserEmail] = CurrentUserEmail,
        REMOVEFILTERS()
    )

RETURN
    IF(
        IsUserGlobalAdmin = TRUE(),
        TRUE(), -- Membuka seluruh baris data bagi admin
        DimOrganization[OrgUnitKey] IN 
            CALCULATETABLE(
                Security_UserAssignment[OrgUnitKey],
                Security_UserAssignment[UserEmail] = CurrentUserEmail,
                REMOVEFILTERS(DimOrganization)
            )
    )
```

#### B. TMSL Script: Penerapan Object-Level Security (OLS)
Skrip Tabular Model Scripting Language (TMSL) untuk mengunci kolom sensitif (misal: `Salary` pada tabel `DimEmployee`) untuk Role `ExternalAnalyst`.

```json
{
  "createOrReplace": {
    "object": {
      "database": "EnterpriseAnalytics_DB",
      "role": "ExternalAnalyst"
    },
    "role": {
      "name": "ExternalAnalyst",
      "modelPermission": "read",
      "tablePermissions": [
        {
          "name": "DimEmployee",
          "columnPermissions": [
            {
              "name": "BaseSalary",
              "metadataPermission": "none"
            },
            {
              "name": "BonusAmount",
              "metadataPermission": "none"
            }
          ]
        },
        {
          "name": "FactPayroll",
          "metadataPermission": "none"
        }
      ]
    }
  }
}
```

#### C. Python Enterprise Automation Engine
Skrip otomasi untuk audit kepatuhan tenant: Mengambil log aktivitas tenant, mendeteksi artefak yang tidak memiliki label sensitivitas Purview, dan memeriksa workspace tanpa kontrol admin (orphan workspaces).

```python
"""
Power BI Enterprise Governance & Audit Engine
Menggunakan Microsoft Entra ID App Registration (Service Principal).
Dependensi: pip install msal requests pydantic
"""

import os
import sys
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import requests
from pydantic import BaseModel, Field

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("PowerBIGovernance")

class TenantConfig(BaseModel):
    tenant_id: str = Field(..., description="Azure Entra ID Tenant ID")
    client_id: str = Field(..., description="Service Principal Application ID")
    client_secret: str = Field(..., description="Service Principal Secret")
    authority_url: str = Field("https://login.microsoftonline.com", description="Entra ID URL")
    scope: List[str] = Field(["https://analysis.windows.net/powerbi/api/.default"])

class ArtifactAuditResult(BaseModel):
    workspace_id: str
    workspace_name: str
    artifact_id: str
    artifact_name: str
    artifact_type: str
    has_sensitivity_label: bool
    label_id: Optional[str] = None
    compliance_violation: bool

class PowerBIEnterpriseAuditor:
    def __init__(self, config: TenantConfig):
        self.config = config
        self.access_token: Optional[str] = None
        self.token_expiry: datetime = datetime.min
        self.base_url = "https://api.powerbi.com/v1.0/myorg"

    def _get_bearer_token(self) -> str:
        """Mengambil token otentikasi via MSAL Client Credentials Flow."""
        if self.access_token and datetime.now() < self.token_expiry:
            return self.access_token

        logger.info("Memperbarui OAuth2 access token via Entra ID...")
        token_endpoint = f"{self.config.authority_url}/{self.config.tenant_id}/oauth2/v2.0/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "scope": " ".join(self.config.scope)
        }
        
        try:
            response = requests.post(token_endpoint, data=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            self.access_token = data["access_token"]
            expires_in = int(data.get("expires_in", 3600))
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)
            return self.access_token
        except requests.exceptions.RequestException as e:
            logger.error("Otentikasi Entra ID gagal: %s", str(e))
            raise ConnectionError(f"Gagal mengambil token Entra ID: {e}")

    def _api_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Melakukan pemanggilan API dengan validasi status dan penanganan exponential backoff."""
        token = self._get_bearer_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        max_retries = 3
        backoff_delay = 5  # detik
        
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.request(method, url, headers=headers, params=params, timeout=60)
                
                # Handling rate limits (HTTP 429 Too Many Requests)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", backoff_delay))
                    logger.warning("Throttled (429). Menunggu %s detik (Percobaan %d/%d)...", retry_after, attempt, max_retries)
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    logger.error("Request API gagal definitif pada URL: %s - Error: %s", url, str(e))
                    raise
                logger.warning("Kegagalan API transient: %s. Retry dalam %s detik...", str(e), backoff_delay)
                time.sleep(backoff_delay)
                backoff_delay *= 2

        raise RuntimeError(f"Gagal mengeksekusi request ke {url} setelah {max_retries} percobaan.")

    def audit_datasets_purview_labels(self) -> List[ArtifactAuditResult]:
        """
        Memeriksa seluruh dataset di seluruh workspace tenant menggunakan Power BI Admin Scanner API.
        Mendeteksi dataset yang tidak memiliki Purview Sensitivity Label.
        """
        logger.info("Memulai audit kepatuhan Sensitivity Labels pada tenant...")
        audit_results: List[ArtifactAuditResult] = []

        # Mengambil daftar semua workspaces di tenant (Admin endpoint)
        endpoint = "admin/groups?$top=100&$filter=type eq 'Workspace'"
        workspaces_data = self._api_request("GET", endpoint)
        workspaces = workspaces_data.get("value", [])

        for ws in workspaces:
            ws_id = ws["id"]
            ws_name = ws.get("name", "Unknown")
            
            # Abaikan workspace Personal pengguna
            if ws.get("isOnDedicatedCapacity") is False and "Personal" in ws_name:
                continue

            logger.info("Mengaudit Workspace: %s (ID: %s)", ws_name, ws_id)
            datasets_endpoint = f"admin/groups/{ws_id}/datasets"
            try:
                ds_data = self._api_request("GET", datasets_endpoint)
                datasets = ds_data.get("value", [])

                for ds in datasets:
                    ds_id = ds["id"]
                    ds_name = ds.get("name", "Unnamed Dataset")
                    
                    # Cek keberadaan sensitivity label
                    sensitivity_info = ds.get("sensitivityLabel")
                    has_label = sensitivity_info is not None and "labelId" in sensitivity_info
                    label_id = sensitivity_info.get("labelId") if has_label else None

                    # Violation: Semantic model enterprise wajib memiliki label sensitivitas
                    violation = not has_label

                    audit_results.append(
                        ArtifactAuditResult(
                            workspace_id=ws_id,
                            workspace_name=ws_name,
                            artifact_id=ds_id,
                            artifact_name=ds_name,
                            artifact_type="Dataset",
                            has_sensitivity_label=has_label,
                            label_id=label_id,
                            compliance_violation=violation
                        )
                    )
            except requests.exceptions.HTTPError as err:
                logger.warning("Gagal mengaudit dataset pada workspace %s: %s", ws_id, str(err))
                continue

        return audit_results

    def get_tenant_activity_audit_events(self, target_date: datetime) -> List[Dict[str, Any]]:
        """
        Mengekstrak log aktivitas tenant untuk audit forensik keamanan (24 jam window).
        """
        start_time = target_date.strftime("%Y-%m-%dT00:00:00.000Z")
        end_time = target_date.strftime("%Y-%m-%dT23:59:59.999Z")
        logger.info("Mengekstraksi Audit Event untuk periode: %s s.d %s", start_time, end_time)

        endpoint = f"admin/activityevents?startDateTime='{start_time}'&endDateTime='{end_time}'"
        events: List[Dict[str, Any]] = []

        while endpoint:
            data = self._api_request("GET", endpoint)
            batch = data.get("activityEventEntities", [])
            events.extend(batch)
            
            # Jika pagination token tersedia, lanjutkan pengambilan
            continuation_uri = data.get("continuationUri")
            if continuation_uri:
                # Ambil endpoint relatif dari URI kelanjutan
                endpoint = continuation_uri.replace(self.base_url, "").lstrip("/")
            else:
                endpoint = ""

        logger.info("Total event audit ditemukan: %d", len(events))
        return events

# Contoh eksekusi (Production Entry Point)
if __name__ == "__main__":
    # Menarik konfigurasi dari environment variables untuk keamanan
    config = TenantConfig(
        tenant_id=os.getenv("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000"),
        client_id=os.getenv("AZURE_CLIENT_ID", "11111111-1111-1111-1111-111111111111"),
        client_secret=os.getenv("AZURE_CLIENT_SECRET", "mock-secret-not-valid")
    )

    auditor = PowerBIEnterpriseAuditor(config)

    try:
        # Jalankan validasi label
        violations = auditor.audit_datasets_purview_labels()
        non_compliant = [v for v in violations if v.compliance_violation]
        
        logger.info("Audit selesai. Ditemukan %d dataset dengan pelanggaran kepatuhan keamanan.", len(non_compliant))
        for item in non_compliant:
            logger.warning(
                "VIOLATION: Workspace [%s] - Dataset [%s] TIDAK memiliki Sensitivity Label!",
                item.workspace_name,
                item.artifact_name
            )
    except Exception as e:
        logger.critical("Fatal error pada eksekusi audit: %s", str(e), exc_info=True)
```

---

### 7. Edge Cases & Failure Modes

#### 1. RLS Role Bypass via Workspace Permissions
- **Failure Mode**: Pengguna yang seharusnya dibatasi oleh RLS dapat melihat seluruh baris data.
- **Root Cause**: Pengguna memiliki role *Admin*, *Member*, atau *Contributor* di dalam Workspace. Dalam arsitektur Power BI, RLS **hanya** berlaku untuk akun yang memiliki role *Viewer*. Akun dengan izin edit otomatis mengabaikan aturan RLS.
- **Remediasi**: Terapkan arsitektur *Decoupled Workspaces*. Workspace Data (hanya dikelola tim data terisolasi) memisahkan laporan ke Workspace Reporting. Konsumen bisnis hanya diberikan akses *Viewer* atau diizinkan melihat melalui Power BI Apps saja.

#### 2. Visual Breaking Akibat OLS (Object-Level Security)
- **Failure Mode**: Laporan menampilkan error visual secara masif (`Visual has an error: Column not found`) alih-alih menampilkan visual secara rapi tanpa kolom rahasia.
- **Root Cause**: OLS menyembunyikan kolom sepenuhnya dari engine skema. Jika sebuah visual tabel merujuk pada `DimEmployee[Salary]` dan pengguna berada di role yang menyembunyikan kolom ini, seluruh visual akan gagal di-render.
- **Remediasi**: Pisahkan visual sensitif ke dalam tab laporan terpisah dengan akses terbatas, atau gunakan pola *Conditional DAX Measures* yang mengembalikan `BLANK()` jika pengguna tidak memiliki izin, alih-alih mengandalkan pemotongan metadata OLS secara langsung untuk atribut agregasi publik.

#### 3. Dynamic RLS Throttling pada VertiPaq
- **Failure Mode**: Visual kartu dan matriks mengalami *query timeout* (300+ detik) pada dataset DirectQuery atau Import berukuran besar (>50 juta baris).
- **Root Cause**: Menggunakan fungsi DAX non-sargable seperti evaluasi regex atau filter berantai dengan relasi many-to-many antara security matrix dan business tables yang dievaluasi secara dinamis pada tiap interaksi visual.
- **Remediasi**: Normalisasi tabel pemetaan. Simpan `UserPrincipalName` secara denormalisasi di tabel dimensi hierarki terendah jika volume data sangat masif, atau gunakan skema *Composite Model* dengan agregasi yang sudah di-cache.

#### 4. Token Expiration pada Long-running Activity Audit Jobs
- **Failure Mode**: Script Python berhenti dengan error `401 Unauthorized` setelah berjalan selama 60 menit saat mengekstraksi audit log harian berukuran gigabytes.
- **Root Cause**: Access Token OAuth2 Entra ID memiliki lifetime default 60 menit. Jika request loop pagination API melebihi waktu ini, otentikasi akan ditolak.
- **Remediasi**: Mengimplementasikan pengecekan masa aktif token sebelum setiap pemanggilan API dan otomatis melakukan token refresh (sudah ditangani pada kelas `PowerBIEnterpriseAuditor._get_bearer_token`).

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi | Dynamic RLS (DAX) | Object-Level Security (OLS) | Pemisahan Workspace / Model |
| :--- | :--- | :--- | :--- |
| **Granularitas** | Level Baris (*Horizontal Filtering*) | Level Kolom & Tabel (*Schema Masking*) | Level Dataset & Seluruh Objek |
| **Dampak Performa** | Meningkatkan komputasi Formula Engine; jika salah rancang, query melambat drastis. | Tidak ada penalti komputasi; model metadata langsung dipangkas saat query parsing. | Performa maksimal karena tiap dataset memiliki ukuran footprint yang spesifik. |
| **Kompleksitas Manajemen** | Menengah; butuh pemeliharaan security matrix table di data pipeline. | Tinggi; butuh alat pihak ketiga (Tabular Editor / TMSL) & deployment pipeline TOM. | Sangat Tinggi; redundansi ETL, duplikasi dataset, dan biaya storage membengkak. |
| **User Experience** | Halus; visual menyesuaikan baris yang diotorisasi tanpa error visual. | Kasar jika salah desain; visual yang memuat kolom OLS akan memunculkan pesan error. | Terisolasi secara bersih; pengguna hanya melihat laporan yang relevan di App mereka. |
| **Use Case Utama** | Pembatasan geografis, divisi, hierarki organisasi penjualan. | Penyembunyian PII, data kompensasi, formula margin keuntungan rahasia. | Pembatasan regulasi tingkat tinggi (misal: Data Negara A vs Negara B yang dilarang tercampur). |

---

### 9. Best Practices & Standar Industri

1. **Prinsip Least Privilege pada Tenant Settings**:
   - Matikan opsi *"Export data to Excel"* untuk *Entire Organization*. Alokasikan hanya ke satu security group khusus (misal: `SG_PBI_DataExporters`).
   - Matikan *"Publish to Web"* secara permanen di level tenant kecuali untuk use case portal publik yang disetujui tim Enterprise Architecture.
2. **Microsoft Purview Automated Label Inheritance**:
   - Pasang integrasi Purview Information Protection pada tenant.
   - Tetapkan *Default Sensitivity Label* (misal: `Internal - General Business`) sehingga dataset baru secara otomatis terproteksi saat dipublikasikan.
3. **Pemisahan Peran melalui Entra ID Security Groups**:
   - Jangan pernah menetapkan izin workspace atau RLS langsung ke alamat email personal (`user@company.com`).
   - Selalu map ke Entra ID Security Groups (misal: `SG_PBI_Finance_Viewers`). Hal ini memindahkan tata kelola lifecycle akun langsung ke sistem Identity Management / HR Onboarding.
4. **Enkripsi Kunci Mandiri (Customer-Managed Keys - CMK)**:
   - Untuk industri perbankan dan kesehatan, implementasikan Azure Key Vault Bring-Your-Own-Key (BYOK) untuk mengenkripsi data at-rest pada storage VertiPaq.
5. **Continuous Compliance Auditing**:
   - Jadwalkan pipeline otomatis (Azure Function atau Python worker mingguan) untuk menarik log via *Admin Activity Event API* dan menyimpannya ke Azure Log Analytics atau Fabric Lakehouse untuk analisis anomali (misal: lonjakan ekspor data mendadak di akhir pekan).

---

### 10. Hands-on Lab Exercise: Implementasi Dynamic RLS dan Kepatuhan Audit

#### Skenario Lab
Anda adalah Lead Data Governance Engineer di sebuah bank multinasional. Anda ditugaskan untuk:
1. Memodelkan Dynamic RLS pada dataset penjualan kartu kredit agar manajer cabang hanya dapat melihat transaksi dari cabang mereka sendiri.
2. Mengamankan kolom `CreditScore` agar tidak dapat diakses oleh analis magang menggunakan TMSL/OLS.
3. Menjalankan skrip Python untuk memastikan tidak ada dataset yang tidak terlabel di workspace cabang.

#### Langkah 1: Siapkan Schema Star & Security Matrix pada Power BI
1. Buka Power BI Desktop.
2. Buat tabel inline DAX `SecurityUserMapping` dengan data berikut:
```dax
SecurityUserMapping = DATATABLE(
    "UserEmail", STRING,
    "BranchCode", STRING,
    {
        {"lead_auditor@company.com", "ALL"},
        {"manager_jkt@company.com", "JKT01"},
        {"manager_sby@company.com", "SBY01"}
    }
)
```
3. Buat tabel dimensi `DimBranch`:
```dax
DimBranch = DATATABLE(
    "BranchCode", STRING,
    "BranchName", STRING,
    {
        {"JKT01", "Jakarta Thamrin"},
        {"SBY01", "Surabaya Tunjungan"},
        {"BDG01", "Bandung Merdeka"}
    }
)
```
4. Buat tabel fakta `FactCreditCardApplication`:
```dax
FactCreditCardApplication = DATATABLE(
    "AppID", INTEGER,
    "BranchCode", STRING,
    "ApplicantName", STRING,
    "CreditScore", INTEGER,
    "LimitRequested", DOUBLE,
    {
        {1001, "JKT01", "Budi Santoso", 750, 50000000},
        {1002, "JKT01", "Ani Wijaya", 620, 20000000},
        {1003, "SBY01", "Citra Dewi", 800, 100000000},
        {1004, "BDG01", "Doni Prasetyo", 580, 15000000}
    }
)
```
5. Buat relasi 1-to-many dari `DimBranch[BranchCode]` ke `FactCreditCardApplication[BranchCode]`. Jangan hubungkan `SecurityUserMapping` secara fisik ke tabel lain.

#### Langkah 2: Buat Dynamic RLS Rule pada Power BI Desktop
1. Masuk ke tab **Modeling** -> **Manage Roles**.
2. Klik **Create Role**, beri nama: `DynamicBranchAccessRole`.
3. Pada tabel `DimBranch`, masukkan formula DAX filter berikut:
```dax
VAR UserEmail = USERPRINCIPALNAME()
VAR IsGlobalAccess = 
    CALCULATE(
        COUNTROWS(SecurityUserMapping),
        SecurityUserMapping[UserEmail] = UserEmail,
        SecurityUserMapping[BranchCode] = "ALL"
    ) > 0

VAR UserAllowedBranches = 
    CALCULATETABLE(
        VALUES(SecurityUserMapping[BranchCode]),
        SecurityUserMapping[UserEmail] = UserEmail
    )

RETURN
    IF(
        IsGlobalAccess,
        TRUE(),
        DimBranch[BranchCode] IN UserAllowedBranches
    )
```
4. Klik **Save**.
5. Uji peran dengan mengklik **View as Roles**.
   - Centang `DynamicBranchAccessRole`.
   - Centang **Other user** dan masukkan: `manager_jkt@company.com`.
   - Verifikasi visual: Hanya data cabang `JKT01` (Budi Santoso dan Ani Wijaya) yang ditampilkan.

#### Langkah 3: Konfigurasi OLS via Tabular Editor
1. Pada Power BI Desktop, buka **External Tools** -> **Tabular Editor**.
2. Di panel Tabular Editor, pilih folder **Roles** -> buat role baru: `InternAnalystRole`.
3. Di tab **Model Permission**, setel ke `Read`.
4. Buka **Tables** -> `FactCreditCardApplication` -> **Columns** -> pilih `CreditScore`.
5. Di panel properties (kanan bawah), cari **Object Level Security** -> set nilai untuk `InternAnalystRole` menjadi `None`.
6. Simpan perubahan ke Semantic Model (Ctrl + S) dan tutup Tabular Editor.
7. Validasi: Buka **View as Roles**, pilih `InternAnalystRole`. Visual yang mencoba membaca `CreditScore` akan memunculkan kalkulasi error/unresolved field, membuktikan penguncian OLS berhasil.

#### Langkah 4: Validasi Kepatuhan Governance secara Programatik
1. Salin implementasi skrip Python dari **Section 6.C**.
2. Siapkan file `.env` yang memuat `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, dan `AZURE_CLIENT_SECRET`.
3. Jalankan skrip audit:
```bash
python pbi_auditor.py
```
4. Periksa log terminal: Sistem akan mencatat dataset mana saja di tenant Anda yang belum mematuhi aturan enkripsi label Microsoft Purview. Pastikan status kepatuhan terverifikasi 100% sebelum mempublikasikan model ke production.