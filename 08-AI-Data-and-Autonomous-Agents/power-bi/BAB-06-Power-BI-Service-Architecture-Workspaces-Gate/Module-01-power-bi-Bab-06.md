# Bab 06: Power BI Service Architecture, Workspaces & Gateways

## Module 01: Arsitektur Cloud Power BI, Tata Kelola Modern Workspaces, dan High-Availability Data Gateways

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Arsitektur Internal Power BI Service**: Menguraikan interaksi antara *Web Front End* (WFE), *Back-End Cluster*, *Azure API Management*, *Azure Relay*, dan penyimpanan metadata (*Azure SQL* & *Azure Data Lake Storage Gen2*).
- **Merancang Desain Tata Kelola Modern Workspaces (v2)**: Mengonfigurasi arsitektur workspace enterprise dengan segregasi hak akses granular berbasis *Role-Based Access Control* (RBAC) dan integrasi *Microsoft Entra ID* (dahulu Azure AD) Groups.
- **Mengimplementasikan Arsitektur High-Availability (HA) On-Premises Data Gateway**: Membangun, mengonfigurasi, dan mengoptimalkan kluster gateway multi-node untuk beban kerja *DirectQuery* dan *Scheduled Refresh* dengan mekanisme failover otomatis.
- **Mengotomatisasi Workspace Lifecycle & Gateway Binding**: Mengembangkan skrip otomasi skala produksi menggunakan Python dan Power BI REST API untuk *provisioning* workspace, penugasan kapasitas, pengikatan dataset ke gateway, serta pemantauan refresh.
- **Memitigasi Resiko Keamanan Jaringan dan Performa Gateway**: Mengidentifikasi titik kegagalan (*bottlenecks*), mengonfigurasi *Kerberos Constrained Delegation* (KCD) untuk *Single Sign-On* (SSO), dan mengatasi limitasi kapasitas resource engine mashup.

---

### 2. Concept Overview

Power BI Service bukan sekadar portal visualisasi berbasis web, melainkan sebuah platform *Software-as-a-Service* (SaaS) terdistribusi berskala masif yang dibangun di atas fondasi komputasi awan Microsoft Azure. Memahami arsitektur internalnya menjadi prasyarat mutlak bagi arsitek data untuk membangun platform analitik yang aman, memiliki latensi rendah, dan *resilient*.

```
+-----------------------------------------------------------------------------------+
|                                POWER BI CLOUD SAAS                                |
|                                                                                   |
|  [ Azure Traffic Manager ]                                                        |
|           │                                                                       |
|           ▼                                                                       |
|  [ Web Front End (WFE) Cluster ] ──(Auth/Routing)──► [ Microsoft Entra ID ]       |
|           │                                                                       |
|           ▼                                                                       |
|  [ Back-End Cluster ]                                                             |
|    ├── API Management Gateway                                                     |
|    ├── Analysis Services Engine (VertiPaq in Cloud)                               |
|    ├── Azure SQL Metadata DB                                                      |
|    └── Azure Data Lake Storage Gen2 (PBI Datamart / Dataflows)                    |
+───────────┬───────────────────────────────────────────────────────────────────────+
            │ Outbound TLS Connection (via Port 443 / 5671)
            ▼
+───────────────────────────────────────────────────────────────────────────────────+
|                                AZURE RELAY / SERVICE BUS                          |
+───────────────────────────────────────────────────────────────────────────────────+
            ▲
            │ Long-polling Outbound Reverse Proxy
+───────────┴───────────────────────────────────────────────────────────────────────+
|                             ENTERPRISE ON-PREMISES / PRIVATE CLOUD                |
|                                                                                   |
|  [ On-Premises Data Gateway Cluster ]                                             |
|    ├── Gateway Node 01 (Primary)   ◄─── Heartbeat / Load Balancing ───► Node 02  |
|    └── Mashup Engine (Evaluation Container)                                       |
|           │                                                                       |
|           ▼ (Kerberos / Basic / OAuth)                                            |
|  [ Local Data Sources: SQL Server, SAP HANA, Oracle, Network Shares ]             |
+-----------------------------------------------------------------------------------+
```

#### Mental Model: The Reverse Proxy Control Plane
Banyak praktisi keliru mengira bahwa cloud Power BI "masuk" ke jaringan internal perusahaan untuk membaca data. Kenyataannya, **On-Premises Data Gateway bekerja sebagai reverse-proxy berbasis outbound connection**. 

Gateway yang diinstal di dalam perimeter jaringan Anda secara proaktif membuka koneksi keluar (*outbound long-polling*) ke Azure Service Bus/Relay. Ketika query dijadwalkan atau query DirectQuery masuk:
1. Power BI Service menaruh payload query terenkripsi ke Azure Relay.
2. Gateway lokal menarik payload tersebut dari antrean Azure Relay melalui port HTTPS terproteksi.
3. Gateway mendekripsi query lokal, mengeksekusinya ke sumber data (Database on-premise), mengenkripsi kembali hasilnya, dan mengembalikannya ke Power BI Service melalui jalur komunikasi keluar yang sama. 

Dengan model ini, administrator keamanan jaringan **tidak perlu membuka port inbound firewall** apa pun pada perimeter jaringan perusahaan.

#### Evolusi Workspace: Modern Workspaces (v2)
Modern Workspaces memisahkan dependensi Power BI dari *Microsoft 365 Groups* klasik. Workspace v2 beroperasi sebagai *logical tenant boundary* independen yang terikat langsung ke Azure RBAC melalui Microsoft Entra ID Security Groups. Hal ini memungkinkan segregasi peran analitik yang ketat tanpa menghasilkan overhead pembuatan tim M365, SharePoint sites, atau mailbox yang tidak dibutuhkan.

---

### 3. Why It Matters

Dalam implementasi skala enterprise, kegagalan dalam mengarsitekturi Power BI Service dan Gateways berujung pada:
1. **Security Vulnerabilities & Data Leakage**: Membuka port inbound firewall yang tidak perlu atau memberikan role *Workspace Admin* ke pengembang analitik secara serampangan membuka celah eskalasi hak akses (*privilege escalation*) dan penghapusan artefak produksi.
2. **Single Point of Failure (SPOF)**: Gateway node tunggal yang dipasang pada VM workstation biasa akan *crash* saat beban query analitik melonjak atau saat VM tersebut di-reboot untuk update OS Windows, melumpuhkan seluruh pelaporan eksekutif.
3. **Mashup Spooling Failures**: Eksekusi refresh data besar yang tidak diisolasi pada kluster gateway dapat menghabiskan memori RAM dan ruang disk penyimpanan sementara (*spooling directory*), menyebabkan kegagalan bertingkat (*cascading failure*) pada query lain yang sedang berjalan.
4. **Governance Chaos (Workspace Sprawl)**: Tanpa arsitektur workspace berbasis *Deployment Pipelines* (Development, Test, Production) dan isolasi RBAC, dataset produksi rawan ditimpa oleh eksperimentasi ad-hoc developer.

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur mendalam interaksi komponen Power BI Service, Gateway Cluster, dan Sumber Data On-Premises:

```
+------------------------------------------------------------------------------------+
|                                    USERS & CLIENTS                                 |
|  [ Power BI Desktop ]       [ Power BI Web App ]          [ Mobile / Embedded App] |
+-----------┬───────────────────────────┬───────────────────────────────┬------------+
            │                           │                               │
            └───────────────────────────┼───────────────────────────────┘
                                        │ HTTPS (Port 443)
                                        ▼
+------------------------------------------------------------------------------------+
|                               POWER BI CONTROL PLANE                               |
|                                                                                    |
|   +----------------------------------------------------------------------------+   |
|   |                        Azure Traffic Manager (Global DNS)                  |   |
|   +-------------------------------------+--------------------------------------+   |
|                                         │                                          |
|                                         ▼                                          |
|   +----------------------------------------------------------------------------+   |
|   |              Web Front End (WFE) Cluster (Angular/Static Content)          |   |
|   +-------------------------------------+--------------------------------------+   |
|                                         │                                          |
|                                         ▼                                          |
|   +----------------------------------------------------------------------------+   |
|   |        API Gateway & Cluster Dispatcher (Reverse Proxy, Routing)           |   |
|   +-------------------------------------+--------------------------------------+   |
+-----------------------------------------┼------------------------------------------+
                                          │
                                          ▼
+------------------------------------------------------------------------------------+
|                                POWER BI DATA PLANE                                 |
|                                                                                    |
|  +-----------------------+  +-----------------------+  +------------------------+  |
|  | Modern Workspace      |  | Dataset / Semantic    |  | Premium Capacity VMSS  |  |
|  | - Admin / Member      |  | Model Container       |  | (Analysis Services     |  |
|  | - Contributor/Viewer  |  | (VertiPaq In-Memory)  |  |  Engine Processes)     |  |
|  +-----------------------+  +-----------┬-----------+  +------------------------+  |
|                                         │                                          |
|  +-----------------------+              │ DirectQuery / Refresh Request            |
|  | Storage System        |              ▼                                          |
|  | - Azure SQL (Meta)    |  +-----------------------+                              |
|  | - ADLS Gen2 (Blobs)   |  | Azure Service Bus     |                              |
|  +-----------------------+  | Relay Channel         |                              |
|                             +-----------┬-----------+                              |
+-----------------------------------------┼------------------------------------------+
                                          │ Secure Outbound TLS (TCP 443 / 5671)
                                          ▼
+------------------------------------------------------------------------------------+
|                         ENTERPRISE FIREWALL / PERIMETER                            |
+-----------------------------------------┬------------------------------------------+
                                          │ 
                                          ▼
+------------------------------------------------------------------------------------+
|                    HIGH AVAILABILITY GATEWAY CLUSTER (DMZ / INTRANET)              |
|                                                                                    |
|   +───────────────────────────────────+     +───────────────────────────────────+  |
|   | Gateway Node 1 (Active/Primary)   |     | Gateway Node 2 (Active/Secondary) |  |
|   | ├── Windows Gateway Host Service  |◄───►| ├── Windows Gateway Host Service  |  |
|   | ├── Mashup Engine (Evaluation)    | Sync| ├── Mashup Engine (Evaluation)    |  |
|   | └── Local Spooling Storage        |     | └── Local Spooling Storage        |  |
|   +-----------------┬-----------------+     +-----------------┬-----------------+  |
+---------------------┼─────────────────────────────────────────┼--------------------+
                      │                                         │
       Kerberos KCD / │ Direct TCP (Port 1433/30015)            │
       Encrypted Auth │                                         │
                      ▼                                         ▼
+------------------------------------------------------------------------------------+
|                         ON-PREMISES DATA SOURCES                                   |
|                                                                                    |
|  +-----------------------------+               +--------------------------------+  |
|  | Microsoft SQL Server Cluster|               | SAP HANA / Oracle Enterprise   |  |
|  +-----------------------------+               +--------------------------------+  |
+------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Alur Kerja Query: Scheduled Refresh vs. DirectQuery
1. **DirectQuery Flow**:
   - Pengguna membuka dashboard di Power BI Service.
   - Analysis Services Engine menghasilkan query spesifik untuk sumber data asal (misalnya: T-SQL untuk SQL Server).
   - Query dienkripsi menggunakan kunci publik (*public key*) dari Gateway Cluster yang disimpan di Power BI Service.
   - Query dikirimkan ke antrean Azure Relay. Node gateway yang tersedia menarik (*pulls*) pesan tersebut.
   - Gateway mendekripsi query menggunakan *private key* lokal yang tersimpan secara terisolasi di DPAPI (*Data Protection API*) Windows.
   - *Mashup Engine* (`Microsoft.Mashup.Container.exe`) mengeksekusi query langsung ke database target via ADO.NET/ODBC driver.
   - Hasil streaming data dienkripsi balik dan dikirimkan kembali melalui Azure Relay ke Power BI Service untuk dirender di visual pengguna.

2. **Scheduled Import Refresh Flow**:
   - Power BI Refresh Scheduler memicu operasi orkestrator.
   - Mashup Engine di gateway mengeksekusi query dan melakukan buffering sebagian data di folder *spooling* lokal gateway (`%LOCALAPPDATA%\Microsoft\On-premises data gateway\Spooler`).
   - Data dipadatkan (*compressed*), dienkripsi, dan distreaming ke Power BI Premium Capacity untuk dibentuk kembali ke dalam struktur kolumnar *VertiPaq Engine*.

#### B. Matriks Hak Akses Modern Workspace (v2) RBAC
Isolasi hak akses harus dikelola berdasarkan prinsip *Least Privilege* menggunakan Entra ID Security Groups:

| Kemampuan / Fitur | Admin | Member | Contributor | Viewer |
| :--- | :---: | :---: | :---: | :---: |
| Update/Hapus Workspace | **Ya** | Tidak | Tidak | Tidak |
| Tambah/Hapus Pengguna Workspace | **Ya** | Tidak | Tidak | Tidak |
| Tambah Member/Contributor lain | **Ya** | **Ya** | Tidak | Tidak |
| Publish/Update/Hapus App | **Ya** | **Ya** | Tidak | Tidak |
| Buat/Edit/Hapus Konten (Report, Dataset) | **Ya** | **Ya** | **Ya** | Tidak |
| Schedule Dataset Refresh | **Ya** | **Ya** | **Ya** | Tidak |
| View dan Baca Report / Dashboard | **Ya** | **Ya** | **Ya** | **Ya** |
| Build permission pada dataset (Ad-hoc query) | **Ya** | **Ya** | **Ya** | Opsional* |

*\*Viewer hanya memiliki read-only data view kecuali hak akses "Build" dieksplisitkan.*

#### C. Mekanisme Gateway High Availability & Load Balancing
Dalam sebuah kluster gateway dengan $N$ node:
- **Distribusi Beban (Traffic Distribution)**: Secara *default*, gateway memproses refresh secara acak ke seluruh node yang aktif jika fitur *Load Balancing* diaktifkan.
- **Resource Throttling**: Jika penggunaan CPU node melebihi batas yang dikonfigurasi pada file `Microsoft.PowerBI.DataMovement.Pipeline.GatewayHost.exe.config`:
  $$\text{CPU Utilization} > \text{ResourceThrottleThreshold (default 90\%)}$$
  Maka node tersebut akan menolak tugas baru dan Azure Relay mendistribusikan eksekusi ke node cadangan dalam kluster yang sama.
- **Failover Logic**: Jika *Node 1* gagal merespons heartbeat Azure Relay dalam waktu $300$ detik, Azure Relay secara transparan mengarahkan antrean data pipeline ke *Node 2*.

---

### 6. Production-Ready Code Implementation

Berikut adalah skrip implementasi otomasi enterprise berbasis Python. Skrip ini menangani autentikasi berbasis *Service Principal* (*OAuth2 Client Credentials Grant*), provisioning Modern Workspace, penugasan kapasitas (*Premium/Fabric*), integrasi hak akses RBAC, serta pengikatan (*binding*) Dataset ke Kluster Data Gateway secara terprogram.

```python
"""
Enterprise Power BI Lifecycle & Gateway Orchestrator
Framework automasi untuk administrasi Power BI Service, pengikatan Gateway,
dan monitoring refresh pipeline berskala enterprise.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import requests
from msal import ConfidentialClientApplication

# Konfigurasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("PowerBI-Platform-Architect")


@dataclass(frozen=True)
class AzureServicePrincipalConfig:
    client_id: str
    client_secret: str
    tenant_id: str
    authority_url: str = "https://login.microsoftonline.com"
    scope: str = "https://analysis.windows.net/powerbi/api/.default"

    @property
    def full_authority(self) -> str:
        return f"{self.authority_url}/{self.tenant_id}"


class PowerBIAuthException(Exception):
    """Exception khusus untuk kegagalan autentikasi ke Azure AD."""
    pass


class PowerBIAPIException(Exception):
    """Exception khusus untuk response error dari Power BI REST API."""
    def __init__(self, status_code: int, message: str, payload: Optional[Dict[str, Any]] = None):
        super().__init__(f"Status: {status_code} | Message: {message} | Details: {payload}")
        self.status_code = status_code
        self.payload = payload


class PowerBIEnterpriseClient:
    """Client enterprise-ready untuk eksekusi API Power BI Service."""
    BASE_URL: str = "https://api.powerbi.com/v1.0/myorg"

    def __init__(self, auth_config: AzureServicePrincipalConfig):
        self._auth_config = auth_config
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _get_access_token(self) -> str:
        """Mengakuisisi OAuth2 access token via MSAL dengan validasi masa berlaku."""
        current_time = time.time()
        if self._token and current_time < (self._token_expires_at - 300):
            return self._token

        app = ConfidentialClientApplication(
            client_id=self._auth_config.client_id,
            client_credential=self._auth_config.client_secret,
            authority=self._auth_config.full_authority,
        )

        result = app.acquire_token_for_client(scopes=[self._auth_config.scope])
        if "access_token" in result:
            self._token = str(result["access_token"])
            # MSAL expires_in adalah integer durasi (detik)
            self._token_expires_at = current_time + float(result.get("expires_in", 3600))
            logger.info("Akses token Microsoft Entra ID berhasil diterbitkan/diperbarui.")
            return self._token
        else:
            err = result.get("error_description", result.get("error"))
            raise PowerBIAuthException(f"Autentikasi gagal: {err}")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    def _execute_request(
        self, method: str, endpoint: str, json_data: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """Eksekusi request HTTP dengan pemrosesan rate-limiting & telemetry logging."""
        url = f"{self.BASE_URL}{endpoint}"
        max_retries = 3
        backoff_delay = 5

        for attempt in range(1, max_retries + 1):
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=json_data,
                timeout=30,
            )

            # Menangani penolakan request akibat rate limiting Power BI Service
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", backoff_delay * attempt))
                logger.warning(f"Terkena throttling (429). Menunggu {retry_after} detik sebelum retry...")
                time.sleep(retry_after)
                continue

            if 200 <= response.status_code < 300:
                return response
            
            # Format payload error
            try:
                error_body = response.json()
            except Exception:
                error_body = {"raw": response.text}

            raise PowerBIAPIException(response.status_code, response.reason, error_body)

        raise PowerBIAPIException(429, "Throttling eksesif: Melebihi kuota retry.")

    def create_modern_workspace(self, workspace_name: str) -> str:
        """Membuat modern workspace (v2) baru secara terprogram."""
        logger.info(f"Membuat Modern Workspace: '{workspace_name}'...")
        payload = {"name": workspace_name}
        res = self._execute_request("POST", "/groups?workspaceV2=true", json_data=payload)
        workspace_id: str = res.json()["id"]
        logger.info(f"Workspace berhasil dibuat dengan ID: {workspace_id}")
        return workspace_id

    def assign_user_to_workspace(
        self, workspace_id: str, email_or_sp_id: str, role: str, principal_type: str = "Group"
    ) -> None:
        """
        Menambahkan user, Group, atau Service Principal ke workspace dengan role spesifik.
        Role yang valid: Admin, Member, Contributor, Viewer.
        PrincipalType: User, Group, App.
        """
        valid_roles = ["Admin", "Member", "Contributor", "Viewer"]
        if role not in valid_roles:
            raise ValueError(f"Role '{role}' tidak valid. Harus salah satu dari {valid_roles}")

        payload = {
            "identifier": email_or_sp_id,
            "groupUserAccessRight": role,
            "principalType": principal_type,
        }
        self._execute_request("POST", f"/groups/{workspace_id}/users", json_data=payload)
        logger.info(f"Subjek '{email_or_sp_id}' berhasil ditambahkan ke '{workspace_id}' sebagai '{role}'.")

    def list_gateway_clusters(self) -> List[Dict[str, Any]]:
        """Mengambil seluruh daftar On-Premises Data Gateway clusters yang dapat diakses."""
        res = self._execute_request("GET", "/gateways")
        gateways: List[Dict[str, Any]] = res.json().get("value", [])
        return gateways

    def bind_dataset_to_gateway(
        self, workspace_id: str, dataset_id: str, gateway_id: str, datasource_id: str
    ) -> None:
        """Mengikat Dataset ke Gateway Cluster dan koneksi datasource spesifik."""
        logger.info(f"Mengikat Dataset {dataset_id} ke Gateway {gateway_id}...")
        payload = {
            "gatewayObjectId": gateway_id,
            "datasourceObjectIds": [datasource_id],
        }
        self._execute_request(
            "POST",
            f"/groups/{workspace_id}/datasets/{dataset_id}/Default.BindToGateway",
            json_data=payload,
        )
        logger.info("Dataset berhasil di-bind ke Enterprise Gateway.")

    def trigger_dataset_refresh(self, workspace_id: str, dataset_id: str) -> None:
        """Memicu eksekusi refresh secara asinkron."""
        logger.info(f"Memicu manual refresh untuk dataset: {dataset_id}...")
        self._execute_request("POST", f"/groups/{workspace_id}/datasets/{dataset_id}/refreshes")
        logger.info("Refresh dataset berhasil diantrikan ke backend engine.")

    def poll_refresh_status(
        self, workspace_id: str, dataset_id: str, timeout_seconds: int = 600
    ) -> str:
        """Memantau progres refresh dataset hingga status Completed/Failed."""
        start_time = time.time()
        logger.info(f"Memulai polling status refresh untuk Dataset {dataset_id}...")

        while (time.time() - start_time) < timeout_seconds:
            res = self._execute_request("GET", f"/groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top=1")
            refreshes = res.json().get("value", [])
            
            if not refreshes:
                logger.info("Belum ada histori refresh yang ditemukan.")
                time.sleep(10)
                continue

            latest_refresh = refreshes[0]
            status = latest_refresh.get("status")
            logger.info(f"Status Refresh terkini: {status}")

            if status in ["Completed", "Failed", "Disabled"]:
                if status == "Failed":
                    service_exception = latest_refresh.get("serviceExceptionJson", "No details")
                    logger.error(f"Kegagalan Refresh Detail: {service_exception}")
                return str(status)

            time.sleep(15)

        raise TimeoutError(f"Dataset refresh melebihi batas waktu toleransi ({timeout_seconds} detik).")


# CONTOH IMPLEMENTASI ORKESTRASI
if __name__ == "__main__":
    # Konfigurasi aman berbasis Service Principal (Credentials ditarik dari vault/environment)
    config = AzureServicePrincipalConfig(
        client_id="00000000-0000-0000-0000-000000000000",
        client_secret="your_super_secret_azure_sp_key",
        tenant_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
    )

    client = PowerBIEnterpriseClient(auth_config=config)

    try:
        # 1. Provisioning Workspace Baru
        ws_name = f"Enterprise-Analytics-Ops-{int(time.time())}"
        workspace_id = client.create_modern_workspace(workspace_name=ws_name)

        # 2. Implementasi RBAC: Memberikan hak akses Contributor ke Grup Entra ID Developer
        client.assign_user_to_workspace(
            workspace_id=workspace_id,
            email_or_sp_id="aad-group-analytics-devs@yourdomain.com",
            role="Contributor",
            principal_type="Group",
        )

        # 3. Discovery Gateway Cluster
        clusters = client.list_gateway_clusters()
        logger.info(f"Jumlah Gateway yang terdeteksi: {len(clusters)}")
        
        if clusters:
            target_gateway = clusters[0]["id"]
            logger.info(f"Gateway Aktif Target: {target_gateway}")
            
            # Asumsi ID Dataset dan ID Datasource sudah terdaftar
            # client.bind_dataset_to_gateway(workspace_id, "dataset-guid", target_gateway, "datasource-guid")
            # client.trigger_dataset_refresh(workspace_id, "dataset-guid")
            # final_status = client.poll_refresh_status(workspace_id, "dataset-guid")
            # logger.info(f"Hasil Eksekusi Refresh: {final_status}")

    except PowerBIAPIException as api_err:
        logger.error(f"Kegagalan Operasi API [{api_err.status_code}]: {api_err}")
    except Exception as e:
        logger.critical(f"Kesalahan Fatal System: {str(e)}", exc_info=True)
```

---

### 7. Edge Cases & Failure Modes

#### A. Gateway Node Split-Brain & Jaringan Terputus
- **Gejala**: Salah satu node dalam kluster gateway kehilangan konektivitas ke internet outbound (Azure Relay), namun masih dapat mengakses database internal.
- **Dampak**: Query terjebak pada node yang *stale* dan Service Bus mencoba berulang kali mengirim payload ke node yang mengalami network disconnectivity.
- **Penanganan**: Konfigurasikan TCP Keep-Alive timeout dan pastikan service `PowerBI Gateway Service` di-*restart* secara graceful via automated probe (Powershell Task Scheduler) bila outbound ping ke endpoint Azure Relay (`*.servicebus.windows.net`) gagal berturut-turut selama 3 kali siklus ping 60-detik.

#### B. Mashup Memory Throttling (Evaluator Out of Memory)
- **Gejala**: Error `MashupException: Container was killed by out of memory condition`.
- **Akar Masalah**: Transformasi Power Query (M) yang tidak teroptimasi (*Query Folding gagal*) memaksa Mashup Engine menarik jutaan baris mentah ke disk dan memori RAM VM gateway lokal.
- **Solusi Arsitektural**: Modifikasi file `Microsoft.PowerBI.DataMovement.Pipeline.GatewayHost.exe.config` di setiap node:
  ```xml
  <!-- Batasi alokasi RAM per evaluation container (dalam Megabytes) -->
  <setting name="MashupExecutionMemoryLimit" serializeAs="String">
      <value>4096</value> 
  </setting>
  <!-- Batasi jumlah container paralel agar tidak membebani core CPU -->
  <setting name="MashupDisableThrottling" serializeAs="String">
      <value>False</value>
  </setting>
  ```

#### C. Kerberos Constrained Delegation (KCD) Token Expiration
- **Gejala**: Pengguna menerima pesan error `Impersonation failed for user` saat mengakses report DirectQuery melalui SSO Gateway.
- **Akar Masalah**: Tiket Kerberos TGS (*Ticket-Granting Service*) kedaluwarsa atau terjadi *Service Principal Name* (SPN) mismatch antara Active Directory Domain Services (AD DS) dan nama server lokal.
- **Solusi**: Konfigurasikan Service Account yang menjalankan instance Gateway dengan izin:
  `Trust this user for delegation to specified services only` menggunakan protokol *Use any authentication protocol* (Protocol Transition) pada domain controller perusahaan.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi | On-Premises Data Gateway (Standard Mode) | Virtual Network (VNet) Data Gateway | On-Premises Data Gateway (Personal Mode) |
| :--- | :--- | :--- | :--- |
| **Arsitektur** | Server Bare-Metal / VM yang dikelola mandiri oleh customer. | *Managed PaaS Service* dari Microsoft yang disuntikkan ke Azure VNet. | Desktop app lokal untuk single user non-enterprise. |
| **Beban Pemeliharaan (Ops Overhead)** | **Tinggi**: Harus update patch OS Windows, upgrade versi gateway tiap bulan. | **Nol**: Full-managed oleh Azure; patching dan auto-scaling otomatis. | **Rendah**: Di-host di workstation pengguna. |
| **Kinerja & Latensi** | Bergantung pada hardware VM dan bandwidth koneksi ExpressRoute/Internet lokal. | Sangat cepat untuk resource Azure; terisolasi dalam backbone fabric Azure. | Sangat lambat; dibatasi hardware workstation lokal. |
| **Fitur High-Availability** | **Manual**: Pengguna harus deploy kluster multi-node dan atur konfigurasi load balancing. | **Built-in**: High availability dan scaling diatur oleh Azure infrastructure. | **Tidak Ada**: *Single point of failure*. |
| **DirectQuery & SSO** | Mendukung SSO via Kerberos dan SAML. | Mendukung SSO via Microsoft Entra ID integration. | **Tidak Mendukung** DirectQuery atau SSO. |
| **Use Case Terbaik** | Pusat data on-premises konvensional tanpa koneksi VNet peering langsung. | Cloud architecture modern: Azure Data Lake, Azure SQL, Snowflake di Azure VNet. | POC personal dan eksplorasi data analis mandiri. |

---

### 9. Best Practices & Standar Industri

1. **Topologi Fisik Gateway**:
   - Selalu implementasikan kluster minimal **$N+1$ node** untuk lingkungan *Production*.
   - Letakkan VM Gateway pada subnet yang sama atau sedekat mungkin (latensi $< 1.5\text{ ms}$) dengan server sumber data (Data Warehouse / Database Cluster) untuk meminimalkan *network hop time*.
2. **Spooling Storage Optimization**:
   - Pindahkan lokasi *Spooling Directory* (folder buffering file sementara) dari drive OS (`C:\`) ke drive SSD NVMe khusus berkecepatan tinggi (`D:\` atau `S:\`) dengan mengubah file `Microsoft.PowerBI.DataMovement.Pipeline.GatewayHost.exe.config`.
3. **Pemisahan Jalur Beban Kerja (Dedicated Gateways)**:
   - Pisahkan kluster Gateway untuk pelaporan analitik berbasis **DirectQuery** (butuh latensi sub-detik) dari kluster Gateway untuk **Scheduled Refresh / ETL Heavy** (butuh troughput I/O dan memori besar). Jangan mencampur keduanya dalam node yang sama pada jam kerja sibuk.
4. **Isolasi Workspace Lifecycle**:
   - Larang developer mempublikasikan laporan langsung ke Workspace Production. Gunakan **Deployment Pipelines** (Dev $\rightarrow$ Test $\rightarrow$ Prod).
   - Pastikan service account atau Service Principal yang digunakan untuk CI/CD pipeline berbeda dengan akun pengguna individu.
5. **Konfigurasi Firewall**:
   - Daftarkan secara eksplisit domain Azure IP range (`PowerQueryOnline` dan `AzureActiveDirectory`) ke daftar izinkan (*allowlist*) firewall daripada membuka port ke seluruh internet via wildcard domain.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan sebagai Lead Enterprise Data Architect untuk membangun infrastruktur otomatisasi Power BI:
1. Memverifikasi kesehatan kluster On-Premises Data Gateway yang ada.
2. Mengembangkan workspace deployment berbasis script Python.
3. Mengonfigurasi hak akses Developer dan Data Analyst menggunakan security groups secara otomatis.

#### Prasyarat
- Python 3.10+ terinstal.
- Library dependensi: `pip install msal requests pydantic`.
- Kredensial Azure AD Service Principal dengan role API Power BI Service: `Tenant.Read.All`, `Workspace.ReadWrite.All`.

#### Langkah 1: Siapkan Konfigurasi Lingkungan
Buat file `config.json` lokal (jangan commit file ini ke version control):
```json
{
  "client_id": "YOUR_AZURE_SP_APP_ID",
  "client_secret": "YOUR_AZURE_SP_SECRET",
  "tenant_id": "YOUR_AZURE_TENANT_ID",
  "dev_security_group_id": "sec-group-analyst-id-sample"
}
```

#### Langkah 2: Eksekusi Skrip Provisioning dan Validasi Gateway
Jalankan skrip berikut untuk membuat workspace, mendaftarkan grup analitik, dan membaca status kesehatan kluster gateway.

```python
import json
import logging
from PowerBIEnterpriseClient import PowerBIEnterpriseClient, AzureServicePrincipalConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Lab-Execution")

def execute_lab():
    # 1. Load config
    with open("config.json", "r") as f:
        cfg = json.load(f)

    auth_cfg = AzureServicePrincipalConfig(
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        tenant_id=cfg["tenant_id"]
    )
    client = PowerBIEnterpriseClient(auth_config=auth_cfg)

    # 2. Ambil metadata Gateway Cluster yang tersedia
    logger.info("Memindai gateway cluster yang aktif...")
    gateways = client.list_gateway_clusters()
    
    if not gateways:
        logger.warning("Tidak ada gateway cluster yang ditemukan pada tenant ini. Buat konfigurasi simulasi.")
    else:
        for gw in gateways:
            logger.info(f"Ditemukan Gateway: Name='{gw.get('name')}', ID='{gw.get('id')}', Type='{gw.get('type')}'")

    # 3. Provisioning Workspace Khusus UAT
    target_ws_name = "Finance-Analytics-PROD-Automated"
    ws_id = client.create_modern_workspace(workspace_name=target_ws_name)
    logger.info(f"Workspace baru aktif: {ws_id}")

    # 4. Tambahkan Entra ID Group Developer ke Workspace
    client.assign_user_to_workspace(
        workspace_id=ws_id,
        email_or_sp_id=cfg["dev_security_group_id"],
        role="Viewer",
        principal_type="Group"
    )
    logger.info("RBAC role Viewer berhasil ditetapkan untuk Analytics Developer Group.")

    print("\n================ LAB VERIFICATION REPORT ================")
    print(f"Status Workspace Provisioning : SUCCESS")
    print(f"Target Workspace ID           : {ws_id}")
    print(f"Gateway Nodes Detected        : {len(gateways)}")
    print("=========================================================\n")

if __name__ == "__main__":
    execute_lab()
```

#### Verifikasi Keberhasilan Lab:
1. Masuk ke portal web Power BI Service (`https://app.powerbi.com`).
2. Periksa panel kiri bawah: Modern Workspace `Finance-Analytics-PROD-Automated` harus muncul.
3. Buka menu **Workspace Access**: Pastikan grup security ID yang didaftarkan tertera dengan peran **Viewer**.
4. Di portal admin Power BI (**Admin Portal** $\rightarrow$ **Gateways**): Pastikan gateway cluster dalam keadaan *Online* dengan tanda centang hijau.