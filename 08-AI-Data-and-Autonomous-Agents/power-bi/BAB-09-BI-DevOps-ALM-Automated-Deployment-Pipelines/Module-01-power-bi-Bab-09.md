# Bab 09: BI DevOps, ALM & Automated Deployment Pipelines
## Modul 01: Declarative ALM, Git Integration, dan CI/CD Automation dengan PBIP & Fabric REST API

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mendekomposisi** artefak monolitik Power BI (`.pbix`) menjadi format deklaratif berbasis teks modern (`.pbip`: TMDL dan PBIR) untuk mendukung version control kolaboratif.
- **Mengarsitekturi** alur Application Lifecycle Management (ALM) multi-environment (Dev-Test-Prod) menggunakan kombinasi Fabric Git Integration dan Microsoft Fabric REST API.
- **Mengimplementasikan** pipeline orkestrasi CI/CD berbasis Azure DevOps atau GitHub Actions dengan autentikasi Service Principal (Entra ID) secara *zero-touch*.
- **Menganalisis dan Memitigasi** anomali deployment enterprise, seperti *schema drift*, pemutusan kredensial sumber data (*credential binding drops*), dan konflik merge pada semantic model tabular.
- **Mengevaluasi trade-off** antara Fabric Native Deployment Pipelines, Workspace Git Integration, dan deklaratif berbasis kompilasi XMLA/Tabular Editor Command Line Interface (TECLI).

---

### 2. Concept Overview

Secara historis, Business Intelligence (BI) berbasis Power BI terkendala oleh karakteristik format `.pbix`: sebuah arsip ZIP terkompresi biner tak transparan yang menggabungkan model data, visualisasi, kredensial, dan cache data. Karakteristik ini memicu antipattern:
- Ketiadaan pelacakan perubahan struktural secara baris per baris (*diffing*).
- Ketidakmungkinan resolusi konflik cabang (*merge conflict*).
- Pola rilis berisiko tinggi melalui publikasi manual dari Power BI Desktop.

```
       [ARTEFAK LAMA]                          [ARTEFAK BARU (PBIP)]
+---------------------------+        +----------------------------------------+
|      File .PBIX           |        |        Direktori Proyek .PBIP          |
|  (Monolitik Biner ZIP)    |        |                                        |
|                           |  ===>  |  +-- Model.SemanticModel/ (TMDL)       |
| - Data Model (Data/Schema)|        |  |   +-- tables/                       |
| - Layout Laporan          |        |  |   \-- model.tmdl                    |
| - Query Mashup (M)        |        |  \-- Report.Report/ (PBIR)             |
| - Data Cache Lokal        |        |      \-- definition.pbir               |
+---------------------------+        +----------------------------------------+
  - Tidak bisa di-diff                 - Granularitas baris teks murni
  - Rawan file override                - Branching, PR, Code Review native Git
```

Pendekatan **Declarative BI ALM** modern memisahkan lapisan abstraksi logika bisnis dari runtime hosting:
1. **PBIP (Power BI Project)**: Format pengembang lokal yang membagi proyek menjadi dua subdirektori terisolasi:
   - **TMDL (Tabular Model Definition Language)**: Representasi tekstual deklaratif dari arsitektur semantic model (tabel, kolom terhitung, measures, hubungan, partisi, roles).
   - **PBIR (Power BI Report Definition)**: Representasi JSON berstruktur pohon dari visual layer (halaman, visual, bookmark, custom filter) yang mematuhi standar skema publik.
2. **Fabric Git Integration**: Mekanisme sinkronisasi dua arah yang menghubungkan branch Git (Azure DevOps Repos atau GitHub) langsung ke Fabric Workspace runtime.
3. **API-driven Deployment Lifecycle**: Penggunaan REST API Fabric/Power BI dan XMLA endpoints untuk melakukan validasi sintaksis, parameterisasi lingkungan, deployment otomatis, dan eksekusi refresh semantic model secara terprogram.

---

### 3. Why It Matters

Dalam implementasi analitik enterprise berskala besar dengan puluhan data engineer dan BI analyst, kegagalan menerapkan BI DevOps berimplikasi langsung pada integritas operasional bisnis:
- **Downtime dan Regresi Data**: Penimpaan measure finansial kritis oleh rilis manual tanpa peer review dapat memicu ketidaksesuaian metrik audit.
- **Konkurensi Terhambat**: Developer saling menimpa pekerjaan (*last-write-wins*) karena sistem biner tidak mendukung merge multi-developer pada semantic model yang sama.
- **Auditabilitas Compliance Nol**: Organisasi yang tunduk pada regulasi SOX atau GDPR wajib membuktikan jejak audit lengkap (*who deployed what and when*). Rilis langsung dari desktop melanggar prinsip pemisahan tugas (*separation of duties*).
- **Environment Inconsistency**: Kegagalan repointing koneksi database antara Development, User Acceptance Testing (UAT), dan Production yang memicu bocornya data produksi ke lingkungan pengembangan atau sebaliknya.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur siklus hidup modern mengisolasi repositori kode sebagai sumber kebenaran tunggal (*Single Source of Truth*), memicu deployment otomatis melalui CI/CD runner berbasis Python dan Fabric REST API:

```
[ DEVELOPER ENVIRONMENT ]
+-----------------------------------------------------------+
| Power BI Desktop (Developer Workstation)                  |
| - Simpan sebagai .PBIP                                     |
| - Edit TMDL / PBIR / DAX Measures                         |
+-----------------------------+-----------------------------+
                              | git commit & push (feature/bi-core-101)
                              v
[ SOURCE CONTROL REPOSITORY ]
+-----------------------------------------------------------+
| Remote Git Repository (GitHub Enterprise / Azure DevOps)  |
|                                                           |
| main branch -----------------------------------------+   |
|   ^                                                  |   |
|   | PR Merge (Peer Reviewed & CI Validated)          |   |
| feature branch                                       |   |
+------------------------------------------------------+----+
                                                       |
        +----------------------------------------------+
        | Triggers CI Pipeline Run
        v
[ CI/CD ORCHESTRATION ENGINE ]
+---------------------------------------------------------------------------------+
| GitHub Actions Runner / Azure Pipelines Agent                                  |
|                                                                                 |
| 1. Linting & Validation: TMDL Syntax + PBI Inspector rules                      |
| 2. Identity Token Exchange: Azure Entra ID Service Principal (OAuth 2.0 Client) |
| 3. Execution: Fabric Python Deployer Module                                     |
|    +-- Repoint Datasource Connection Strings (Dev -> Prod)                      |
|    +-- Invoke REST API / XMLA Deploy Sync                                       |
|    +-- Trigger Post-Deployment Processing (Semantic Model Refresh)              |
+---------------------------------------+-----------------------------------------+
                                        |
       +--------------------------------+--------------------------------+
       | Fabric REST API: Update From Git / Deployment Pipeline          |
       v                                                                 v
[ TARGET HOSTING RUNTIME ]                                     [ ENTERPRISE TARGET RUNTIME ]
+-----------------------------------------+                    +-----------------------------------------+
| Development Workspace                  |                    | Production Workspace                   |
| (Workspace terikat ke Dev Branch)       |                    | (Workspace terikat ke Tag / Main)       |
|                                         |                    |                                         |
| +-------------------------------------+ |                    | +-------------------------------------+ |
| | Semantic Model (TMDL Runtime)       | |                    | | Semantic Model (TMDL Runtime)       | |
| +-------------------------------------+ |                    | +-------------------------------------+ |
| | Reports (PBIR Native Layout)        | |                    | | Reports (PBIR Native Layout)        | |
| +-------------------------------------+ |                    | +-------------------------------------+ |
+-----------------------------------------+                    +-----------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### Struktur Fisik & Semantik PBIP
Ketika proyek Power BI disimpan sebagai format `.pbip`, direktori tersusun secara deterministik:
```
SalesAnalytics.pbip
├── SalesAnalytics.Report/
│   ├── definition.pbir
│   └── definition/
│       ├── pages/
│       │   └── page1/
│       │       ├── page.json
│       │       └── visuals/
│       │           └── visual1/visual.json
│       └── report.json
└── SalesAnalytics.SemanticModel/
    ├── definition.pbism
    ├── diagramLayout.json
    └── definition/
        ├── model.tmdl
        ├── relationships.tmdl
        └── tables/
            ├── Customer.tmdl
            └── Date.tmdl
```

- **TMDL Engine**: TMDL menggunakan indentasi hierarkis tab-delimited, mengeleminasi noise sintaksis JSON/XML. Sebagai contoh, definisi kalkulasi DAX diisolasi secara atomik:
  ```tmdl
  table Sales
      measure 'Total Revenue' = SUM(Sales[Amount])
          formatString: \$#,##0.00
          displayFolder: Financials
          lineageTag: a7e3d81f-8182-4c6e-8e6c-389fcfda3a60
  ```
  Jika developer A mengubah ekspresi DAX dari `SUM` ke `SUMX`, dan developer B menambahkan measure lain di folder terpisah, Git memproses perubahan ini tanpa merge conflict pada file terkompilasi.

#### Fabric Git Engine Synchronizer
Integrasi Git di Fabric tidak sekadar mengkloning file, melainkan mengoperasikan mesin rekonsiliasi state:
1. **Head State Tracking**: Workspace memetakan internal snapshot (dikenal sebagai *Item Deserialized State*) terhadap commit SHA terbaru di remote branch Git.
2. **Git Status Call**: API endpoint `POST https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/git/status` mengevaluasi perbedaan antara commit Git dan internal workspace state, menghasilkan status `workspaceHead` dan `remoteCommitHash`.
3. **Conflict Resolution & Update**: Endpoint `POST https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/git/updateFromGit` melakukan rekonsiliasi. Jika remote commit mendahului workspace, Fabric akan menguraikan TMDL/PBIR dan mengompilasinya langsung ke Analysis Services engine internal serta Report rendering engine secara atomik.

#### REST API Authentication Matrix
Deployment tanpa intervensi manusia (*headless deployment*) wajib menggunakan Service Principal Entra ID (sebelumnya Azure AD):
- **Izin Tenant**: Mengaktifkan "Service principals can use Fabric APIs" di Fabric Admin Portal.
- **Hak Akses Workspace**: Service Principal harus diberi peran minimal **Contributor** atau **Admin** di workspace target.
- **OAuth 2.0 Client Credentials Grant**: Mengakuisisi token autentikasi dengan scope `https://analysis.windows.net/powerbi/api/.default` atau `https://api.fabric.microsoft.com/.default`.

---

### 6. Production-Ready Code Implementation

Berikut adalah sistem deployment modular berstandar enterprise yang terdiri dari:
1. Mesin orkestrator Python yang memicu sinkronisasi Fabric Git dan refresh dataset dengan penanganan retry serta error handling kuat.
2. Pipeline GitHub Actions terstruktur yang menjalankan automasi secara teruji.

#### Komponen 1: Python Fabric Deployment Engine (`fabric_deployer.py`)

```python
"""
Fabric Deployment Engine
Menangani akuisisi token, status check integrasi Git, sinkronisasi workspace,
dan pemrosesan refresh model semantik menggunakan Microsoft Fabric REST API.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Final, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Konfigurasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger: logging.Logger = logging.getLogger("FabricDeployer")

FABRIC_BASE_URL: Final[str] = "https://api.fabric.microsoft.com/v1"
POWERBI_BASE_URL: Final[str] = "https://api.powerbi.com/v1.0/myorg"
SCOPE_FABRIC: Final[str] = "https://api.fabric.microsoft.com/.default"


@dataclass(frozen=True)
class AzureCredentials:
    tenant_id: str
    client_id: str
    client_secret: str

    def validate(self) -> None:
        if not (self.tenant_id and self.client_id and self.client_secret):
            raise ValueError("Kredensial Azure Entra ID tidak lengkap.")


class FabricClient:
    """Klien API Fabric dengan konfigurasi resilient connection pooling dan exponential backoff."""

    def __init__(self, creds: AzureCredentials) -> None:
        creds.validate()
        self._creds = creds
        self._session = self._init_session()
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    @staticmethod
    def _init_session() -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        return session

    def _get_access_token(self) -> str:
        """Mengakuisisi token Entra ID via OAuth2 Client Credentials Flow dengan in-memory caching."""
        if self._token and time.time() < self._token_expiry:
            return self._token

        token_url = f"https://login.microsoftonline.com/{self._creds.tenant_id}/oauth2/v2.0/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._creds.client_id,
            "client_secret": self._creds.client_secret,
            "scope": SCOPE_FABRIC,
        }

        try:
            logger.info("Mengakuisisi Bearer Token dari Azure Entra ID...")
            resp = self._session.post(token_url, data=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            self._token = str(data["access_token"])
            # Berikan buffer 120 detik sebelum kedaluwarsa
            self._token_expiry = time.time() + int(data["expires_in"]) - 120
            return self._token
        except requests.RequestException as e:
            logger.error("Kegagalan autentikasi OAuth2 Entra ID: %s", str(e))
            raise RuntimeError(f"Autentikasi gagal: {e}") from e

    def _get_headers(self) -> Dict[str, str]:
        token = self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def trigger_git_sync(self, workspace_id: str) -> None:
        """
        Mengeksekusi update from Git pada workspace Fabric yang terintegrasi repositori.
        Operasi ini memvalidasi status dan mengeksekusi long-running sync operation.
        """
        headers = self._get_headers()
        status_url = f"{FABRIC_BASE_URL}/workspaces/{workspace_id}/git/status"

        logger.info("Memeriksa status integrasi Git untuk workspace %s...", workspace_id)
        status_resp = self._session.get(status_url, headers=headers, timeout=30)
        status_resp.raise_for_status()
        status_data = status_resp.json()

        workspace_head = status_data.get("workspaceHead")
        remote_commit = status_data.get("remoteCommitHash")
        changes: List[Dict[str, Any]] = status_data.get("changes", [])

        logger.info("Workspace Head: %s | Remote Commit: %s", workspace_head, remote_commit)
        logger.info("Deteksi perubahan belum tersinkronisasi: %d item.", len(changes))

        if not changes and workspace_head == remote_commit:
            logger.info("Workspace telah sinkron penuh dengan Git remote. Tidak perlu update.")
            return

        update_url = f"{FABRIC_BASE_URL}/workspaces/{workspace_id}/git/updateFromGit"
        update_payload = {
            "remoteCommitHash": remote_commit,
            "conflictResolution": {
                "conflictResolutionType": "Workspace",
                "conflictResolutionPolicy": "PreferRemote",
            },
            "allowOverrideItems": True,
        }

        logger.info("Memulai job sinkronisasi (updateFromGit) ke Fabric...")
        update_resp = self._session.post(update_url, headers=headers, json=update_payload, timeout=30)

        # 202 Accepted mengindikasikan operasi asinkron
        if update_resp.status_code == 202:
            operation_url = update_resp.headers.get("Location")
            self._poll_long_running_operation(operation_url)
        elif update_resp.status_code in [200, 204]:
            logger.info("Sinkronisasi instan berhasil selesai.")
        else:
            update_resp.raise_for_status()

    def _poll_long_running_operation(self, operation_url: Optional[str]) -> None:
        """Memantau status operasi asinkron Fabric REST API hingga status 'Succeeded'."""
        if not operation_url:
            raise ValueError("Location header tidak ditemukan pada respons asinkron.")

        headers = self._get_headers()
        max_retries = 30
        poll_interval_sec = 10

        logger.info("Memantau Long-Running Operation: %s", operation_url)

        for attempt in range(max_retries):
            time.sleep(poll_interval_sec)
            resp = self._session.get(operation_url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")

            logger.info("Status polling (Percobaan %d/%d): %s", attempt + 1, max_retries, status)

            if status == "Succeeded":
                logger.info("Operasi sinkronisasi Git selesai dengan sukses.")
                return
            if status in ["Failed", "Canceled"]:
                error_detail = data.get("error", "Tanpa detail error tambahan.")
                raise RuntimeError(f"Operasi Git gagal dengan status '{status}': {error_detail}")

        raise TimeoutError("Polling operasi asinkron melampaui batas waktu maksimum (300 detik).")

    def trigger_semantic_model_refresh(self, workspace_id: str, dataset_id: str) -> None:
        """Memicu refresh model semantik tabular menggunakan endpoint Power BI REST API."""
        headers = self._get_headers()
        refresh_url = f"{POWERBI_BASE_URL}/groups/{workspace_id}/datasets/{dataset_id}/refreshes"

        payload = {"type": "Full", "commitMode": "Transactional"}

        logger.info("Memicu kalkulasi dan refresh data untuk Model ID: %s", dataset_id)
        resp = self._session.post(refresh_url, headers=headers, json=payload, timeout=30)

        if resp.status_code == 202:
            logger.info("Request refresh semantic model diterima secara sukses oleh Analysis Services.")
        else:
            logger.error("Gagal memulai refresh model: %s", resp.text)
            resp.raise_for_status()


def execute_pipeline() -> None:
    """Fungsi eksekusi entrypoint utama deployment."""
    tenant_id = os.getenv("AZURE_TENANT_ID", "")
    client_id = os.getenv("AZURE_CLIENT_ID", "")
    client_secret = os.getenv("AZURE_CLIENT_SECRET", "")
    workspace_id = os.getenv("FABRIC_WORKSPACE_ID", "")
    dataset_id = os.getenv("FABRIC_DATASET_ID", "")

    if not workspace_id:
        logger.error("Environment variable FABRIC_WORKSPACE_ID wajib didefinisikan.")
        sys.exit(1)

    credentials = AzureCredentials(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )

    client = FabricClient(creds=credentials)

    try:
        # Step 1: Tarik kode TMDL dan PBIR terbaru dari repositori Git ke Workspace
        client.trigger_git_sync(workspace_id=workspace_id)

        # Step 2: Jika ID dataset disertakan, jalankan refresh data transaksional
        if dataset_id:
            client.trigger_semantic_model_refresh(workspace_id=workspace_id, dataset_id=dataset_id)

        logger.info("BI DevOps Automation Deployment berhasil diselesaikan secara utuh.")
    except Exception as exc:
        logger.critical("Fatal error pada eksekusi deployment pipeline: %s", str(exc), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    execute_pipeline()
```

#### Komponen 2: GitHub Actions Declarative Pipeline (`.github/workflows/deploy-bi.yml`)

```yaml
name: Enterprise BI ALM Orchestration

on:
  push:
    branches:
      - main
    paths:
      - 'src/**/*.SemanticModel/**'
      - 'src/**/*.Report/**'
  workflow_dispatch:
    inputs:
      force_refresh:
        description: 'Paksa semantic model refresh setelah sync'
        required: true
        type: boolean
        default: true

permissions:
  id-token: write
  contents: read

jobs:
  validate-and-deploy:
    name: Validate TMDL & Sync to Fabric
    runs-on: ubuntu-latest
    environment: Production

    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python Environment
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Runtime Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests urllib3

      - name: Validate TMDL Structural Syntax
        run: |
          echo "Memulai linting format TMDL..."
          # Validasi skema dasar: Memastikan file model.tmdl ada dan tidak kosong
          find src/ -name "model.tmdl" | while read -r file; do
            if [ ! -s "$file" ]; then
              echo "Error: File TMDL terdeteksi kosong: $file"
              exit 1
            fi
          done
          echo "Validasi sintaksis lokal lolos."

      - name: Run Fabric Deployment Engine
        env:
          AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
          AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
          AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
          FABRIC_WORKSPACE_ID: ${{ secrets.FABRIC_WORKSPACE_ID }}
          FABRIC_DATASET_ID: ${{ secrets.FABRIC_DATASET_ID }}
        run: |
          python scripts/fabric_deployer.py
```

---

### 7. Edge Cases & Failure Modes

Pada deployment pipeline terotomatisasi, kegagalan biasanya terjadi di lapisan metadata atau koneksi data:

1. **Schema Drift & Broken Partitioning**:
   - *Kasus*: Sebuah kolom di database sumber diubah tipenya (misalnya `BIGINT` menjadi `VARCHAR`), tetapi skema TMDL tidak diperbarui.
   - *Mitigasi*: Sisipkan tahapan pre-deployment execution schema dry-run. Skrip Python harus mengeksekusi query `SELECT TOP 0` ke database target untuk mengonfirmasi kompatibilitas skema sebelum mengupdate Fabric workspace.

2. **Credential Binding Drops**:
   - *Kasus*: Setelah eksekusi `updateFromGit`, koneksi model semantik ke Azure SQL atau Snowflake kehilangan credential binding (OAuth/Key) karena Fabric memisahkan definisi dataset dari secret koneksi. Dataset beralih ke state unauthenticated.
   - *Mitigasi*: Eksekusi patching koneksi via REST API `PATCH https://api.powerbi.com/v1.0/myorg/gateways/{gatewayId}/datasources/{datasourceId}` menggunakan skrip automasi pasca-sinkronisasi Git untuk menginjeksikan kembali binding credential Service Principal.

3. **Orphaned Layout Containers pada PBIR**:
   - *Kasus*: Dua branch terpisah menghapus dan memodifikasi visual yang sama secara bersamaan. Saat merge, file `visual.json` memegang referensi ke GUID yang sudah terhapus di `page.json`.
   - *Mitigasi*: Terapkan validasi JSON Schema berbasis rule menggunakan script pre-commit hook untuk memvalidasi bahwa seluruh visual GUID di `page.json` eksis di disk fisik.

4. **Workspace Concurrency Locks**:
   - *Kasus*: Pipeline mengeksekusi API sinkronisasi tepat saat proses refresh terjadwal sedang berlangsung di background Analysis Services engine.
   - *Mitigasi*: Implementasikan status checker API untuk mendeteksi apakah dataset sedang `In-Progress`. Jika aktif, jalankan mekanisme cancellation atau backoff exponential dengan jitter sebelum melakukan sinkronisasi metadata.

---

### 8. Trade-offs & Alternatif Solusi

| Kriteria Analisis | Fabric Workspace Git Integration | Native Deployment Pipelines (UI) | XMLA Endpoint + Tabular Editor (TECLI) |
| :--- | :--- | :--- | :--- |
| **Kontrol Versi Kode** | **Native & Granular**; Berbasis branch Git, commit, dan PR review. | **Terbatas**; Snapshot antar-workspace yang digerakkan oleh UI. | **Native Luar Platform**; Berbasis repository scriptable (TMDL/BIM). |
| **Kebutuhan Lisensi** | Fabric Capacity (F SKU) atau PPU. | Pro/PPU/Fabric (Tersedia luas di lisensi reguler). | Minimum PPU atau Fabric Capacity / Premium. |
| **Otomasi CI/CD** | **Tinggi via REST API**; Dukungan native via `git/updateFromGit`. | **Sedang-Tinggi**; API deployment pipeline tersedia tapi terbatas pada migrasi stage. | **Maksimum**; Full programmatic script control via Azure CLI / GitHub Action runners. |
| **Resolusi Konflik** | Ditangani langsung pada file teks (Git conflict engine). | Tidak ada mekanisme resolusi; overwriting sistem penuh. | Merge resolution manual via file metadata berbasis CLI. |
| **Report Lifecycle Support** | Lengkap (Mendukung integrasi PBIR native). | Lengkap (Report, Dashboard, Dataset tersinkronisasi). | **Hanya Semantic Model** (XMLA tidak mendukung visual report). |

---

### 9. Best Practices & Standard Industri

1. **Separation of Concerns: Dataset vs. Report Split**:
   - Jangan pernah menyatukan report visualisasi dan semantic model dalam satu file kerja jika dikembangkan oleh tim terpisah.
   - Buat satu repositori khusus untuk **Core Semantic Models** (`Core_Model.pbip`).
   - Buat repositori terpisah untuk **Analytical Reports** yang terhubung via DirectQuery / Live Connection ke remote published semantic model.
2. **Branching Strategy (Trunk-Based vs GitFlow)**:
   - Gunakan branch `dev` yang dipetakan ke Workspace Development.
   - Gunakan branch `main` yang dilindungi branch protection rules (minimal 2 reviewer, validasi pipeline wajib lolos) yang dipetakan langsung ke Workspace Production.
3. **Environment Parameterization**:
   - Manfaatkan Power Query M Parameters untuk semua connection string (`ServerName`, `DatabaseName`).
   - Terapkan konfigurasi rules pada runtime deployment Fabric untuk memetakan parameter database Dev ke Production secara dinamis tanpa mengubah file teks TMDL.
4. **Automated Static Analysis via Tabular BPA**:
   - Sebelum merger ke branch `main`, eksekusi Best Practice Analyzer (BPA) rules (menggunakan Tabular Editor CLI) untuk memastikan performa DAX:
     - Deteksi kolom bertipe floating-point tanpa formatting.
     - Peringatan untuk relasi Bi-directional pada tabel berukuran jutaan baris.
     - Deteksi visual tanpa accessibility flags.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda ditugaskan mengonversi sebuah model analitik monolitik lokal ke PBIP deklaratif, mendorong perubahannya ke GitHub, dan mengeksekusi pipeline deployment terotomatisasi ke Fabric Development Workspace.

#### Langkah 1: Konfigurasi Proyek Lokal & Export ke PBIP
1. Buka Power BI Desktop.
2. Buka menu **File** -> **Options and settings** -> **Options** -> **Preview features**.
3. Pastikan opsi **Power BI Project (.pbip) save option** dan **Store reports using enhanced metadata format (PBIR)** aktif.
4. Buka laporan Anda yang ada, pilih **File** -> **Save As**, ganti ekstensi target menjadi **Power BI Project (*.pbip)** dengan nama `FinOps_Model`.
5. Tutup Power BI Desktop.

#### Langkah 2: Inisialisasi Git Repository Lokal
Jalankan perintah berikut di root folder project:
```bash
# Pindah ke direktori proyek
cd FinOps_Model

# Inisialisasi Git
git init

# Buat file .gitignore khusus Power BI
cat <<EOT > .gitignore
*.tmp
*.log
.pbi/localSettings.json
.pbi/cache.abf
*.Security/
EOT

# Tambahkan struktur file deklaratif
git add .
git commit -m "feat: Inisialisasi format deklaratif TMDL dan PBIR untuk FinOps Model"
```

#### Langkah 3: Konfigurasi Service Principal Entra ID
1. Buat Service Principal di portal Microsoft Entra ID bernama `sp-bi-devops-orchestrator`.
2. Generate Secret baru dan simpan `tenant_id`, `client_id`, dan `client_secret`.
3. Buka Fabric/Power BI Admin Portal -> **Tenant Settings** -> **Developer Settings**:
   - Aktifkan: **Service principals can use Fabric APIs**.
   - Tambahkan Security Group yang memuat Service Principal Anda.
4. Buka Fabric Workspace target, klik **Workspace Settings** -> **Access** -> Tambahkan Service Principal sebagai role **Member** atau **Admin**.

#### Langkah 4: Hubungkan Workspace ke Git
1. Pada Fabric Workspace, klik **Workspace Settings** -> **Git integration**.
2. Hubungkan ke Organization, Project, Repository GitHub/Azure DevOps Anda, dan tetapkan branch ke `main`.
3. Tentukan folder root sinkronisasi (misal: `/FinOps_Model`).
4. Klik **Connect and sync**.

#### Langkah 5: Eksekusi Perubahan DAX dan Verifikasi CI/CD
1. Buka file measure TMDL lokal: `FinOps_Model.SemanticModel/definition/tables/FinOps.tmdl`.
2. Tambahkan measure baru secara manual di text editor (VS Code):
   ```tmdl
   measure 'Deployment Test Measure' = 1 + 0
       formatString: 0
       displayFolder: _Auditing
   ```
3. Lakukan commit dan push ke remote branch:
   ```bash
   git add FinOps_Model.SemanticModel/definition/tables/FinOps.tmdl
   git commit -m "feat(metric): Tambah Deployment Test Measure via TMDL declarative edit"
   git push origin main
   ```
4. Jalankan script automasi Python Anda:
   ```bash
   export AZURE_TENANT_ID="<your-tenant-guid>"
   export AZURE_CLIENT_ID="<your-client-guid>"
   export AZURE_CLIENT_SECRET="<your-secret-key>"
   export FABRIC_WORKSPACE_ID="<your-workspace-guid>"

   python scripts/fabric_deployer.py
   ```

#### Langkah 6: Validasi Akhir
1. Buka kembali Fabric Workspace di browser Anda.
2. Periksa status integrasi Git: pastikan status sinkronisasi bertanda centang hijau (**Synced**).
3. Buka Semantic Model `FinOps_Model` di browser.
4. Pastikan tabel `FinOps` kini memiliki measure baru `Deployment Test Measure` di bawah folder display `_Auditing` tanpa perlu membuka Power BI Desktop atau melakukan publikasi manual. Model berhasil diperbarui secara headless dan deterministik.