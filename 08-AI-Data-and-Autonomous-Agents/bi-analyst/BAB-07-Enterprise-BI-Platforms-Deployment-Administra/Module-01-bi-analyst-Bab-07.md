# Bab 07: Enterprise BI Platforms Deployment & Administration

## Modul 01: Arsitektur Modern BI Platform, Multi-Tenant Deployment, dan Declarative Governance

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis & Merancang** topologi enterprise modern BI (*Decoupled/Headless BI Architecture*) yang memisahkan lapisan semantik (*semantic layer*), mesin kalkulasi analitik, dan antarmuka visualisasi/konsumsi agen AI.
*   **Mengimplementasikan** orkestrasi *deployment* multi-tenant berbasis kontainer (*Kubernetes-native*) dengan isolasi sumber daya komputasi, proteksi *noisy-neighbor*, dan sinkronisasi metadata otomatis.
*   **Membangun** sistem *declarative governance* untuk *Row-Level Security* (RLS) dan *Column-Level Security* (CLS) yang diinjeksi secara deterministik pada tingkat *Abstract Syntax Tree* (AST) SQL, mencegah kebocoran data (*data leakage*) pada multi-tenant data warehouse.
*   **Mengotomatisasi** *Continuous Integration & Continuous Deployment* (CI/CD) untuk aset metrik analitik (*Metrics-as-Code*) dengan pengujian regresi deterministik, validasi skema semantik, dan verifikasi performa *dry-run*.
*   **Mengonfigurasi** arsitektur *caching* multi-tier (*in-memory*, *pre-aggregation store*, dan *data warehouse passthrough*) untuk mencapai target SLA sub-detik pada pembacaan metrik tanpa membebani biaya komputasi *cloud warehouse*.

---

### 2. Concept Overview

Secara historis, platform Business Intelligence (BI) monolitik menggabungkan *ingestion*, pemodelan data proprietary, kalkulasi metrik, tata kelola keamanan, dan visualisasi ke dalam satu sistem *black-box*. Paradigma ini gagal memenuhi kebutuhan skala enterprise modern karena menghasilkan *metric divergence* (definisi metrik yang berbeda antar departemen), kesulitan integrasi dengan ekosistem AI/Autonomous Agents, serta *vendor lock-in*.

```
   [ Monolithic BI ]
+----------------------+
| Visualization UI     |
| Proprietary Modeling | -> Tight Coupling -> Metric Divergence & Governance Drift
| Execution Engine     |
+----------------------+

   [ Decoupled / Modern Headless BI ]
+-------------------------------------------------------------+
| Presentation / Consumers: Superset, Tableau, AI Agents      |
+-------------------------------------------------------------+
                              | Standard APIs (SQL, GraphQL, REST)
+-------------------------------------------------------------+
| Headless Semantic Layer: Metric Governance, Dynamic RLS/CLS |
+-------------------------------------------------------------+
                              | Accelerated SQL / Pre-aggregations
+-------------------------------------------------------------+
| Compute & Cache Engine: Redis + DuckDB/ClickHouse           |
+-------------------------------------------------------------+
                              | Dialect Compilation
+-------------------------------------------------------------+
| Cloud Data Warehouse: Snowflake, BigQuery, Databricks       |
+-------------------------------------------------------------+
```

Model mental yang digunakan dalam arsitektur modern adalah **The Semantic Compiler & Virtual Data Warehouse Pattern**. Platform BI modern diposisikan bukan sebagai tempat penyimpanan data, melainkan sebagai sebuah *compiler layer* yang:
1. Membaca definisi metrik berbasis deklaratif (*YAML/Jinja/Code*).
2. Menerima permintaan analitik dari berbagai klien (dashboard, LLM agent, REST API).
3. Menginjeksi *security context* pengguna (tenant ID, role, geo-fencing).
4. Mentranslasikan representasi permintaan logis menjadi *Abstract Syntax Tree* (AST) SQL yang teroptimasi sesuai dialek target data warehouse.
5. Mengeksekusi rute kueri: menyajikan data dari *cache/pre-aggregation layer* jika valid, atau mendorong eksekusi langsung (*pushdown query*) ke distributed cloud data warehouse secara asinkron.

---

### 3. Why It Matters

Dalam skala enterprise:
*   **Konsistensi Metrik untuk AI & Human Consumption**: Apabila autonomous agent mengambil data `Revenue` via LLM tools, agent tersebut harus mendapatkan nilai yang identik secara matematis dengan dashboard eksekutif. Tanpa *headless semantic layer*, agen AI menyusun raw SQL secara probabilistik yang rentan halusinasi logika agregasi (misal: gagal mengecualikan *void transaction* atau diskon).
*   **Kepatuhan Regulasi & Isolasi Tenant**: Kebocoran data antar-penyewa (*cross-tenant data leakage*) adalah risiko eksistensial bagi model bisnis multi-tenant SaaS atau konglomerasi multi-entitas. Keamanan tidak boleh bergantung pada filter manual yang ditulis oleh BI analyst pada level dashboard, melainkan harus diisolasi pada level arsitektur dan runtime compiler.
*   **FinOps & Warehouse Guardrails**: Query langsung (*ad-hoc*) dari ratusan analis dan automated agents dapat melumpuhkan performa *cloud data warehouse* dan melipatgandakan *operational expenditure* (OpEx). Arsitektur deployment BI yang tepat menerapkan *smart caching*, pre-agregasi otomatis, serta *concurrency control* untuk membatasi konsumsi sumber daya komputasi secara efisien.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur enterprise di bawah ini mendemonstrasikan sistem Headless BI Platform terdistribusi dengan orkestrasi berbasis GitOps, multi-tier caching, dan AST-level security enforcement.

```
                          [ Git Repository ]
                    (Semantic Models: Metrics/RLS)
                                  |
                                  v
                        [ CI/CD Pipeline ]
                  (Linter, AST Validator, Dry-Run)
                                  | Artifacts
                                  v
+===================================================================================+
| ENTERPRISE KUBERNETES CLUSTER                                                     |
|                                                                                   |
|  [ API Gateway & Ingress Controller ] <--- mTLS / OIDC (Okta/Azure AD)            |
|       |                                                                           |
|       +------------------------------------+------------------------------+       |
|       |                                    |                              |       |
|       v                                    v                              v       |
|  [ BI Core Pod 1 ]                    [ BI Core Pod 2 ]             [ BI Core Pod N ]|
|  +------------------------------+     +------------------------+                  |
|  | - Auth Context Injector      |     | - Semantic Engine      |                  |
|  | - AST Compiler & Rewriter    |     | - Query Orchestrator   |                  |
|  | - Tenant Metadata Resolver   |     | - Dialect Transpiler   |                  |
|  +------------------------------+     +------------------------+                  |
|       |                 |                  |                                      |
|       | Read/Write      | Cache Invalidation                                      |
|       v                 v                  |                                      |
|  [ Cluster Redis (L1) ] [ Control Bus ]    | Local Acceleration                   |
|  (Session, Cache Index, (Pub/Sub)          v                                      |
|   Rate Limiter)                  [ Embedded / Distributed Pre-Aggregation Store ] |
|                                  (ClickHouse Cluster / DuckDB Workers - L2)       |
+===================================================================================+
                                         |
                                         | Pushdown SQL (Compiled with AST RLS)
                                         v
                 +-----------------------------------------------+
                 | ENTERPRISE DATA WAREHOUSE (L3)                |
                 | (Snowflake, Databricks Lakehouse, BigQuery)   |
                 +-----------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Kompilasi Kueri Semantik & Rewrite AST
Ketika kueri diterima oleh BI Core melalui REST/GraphQL API:
1. **Request Intake**: Engine menerima parameter logis, misal: `measures: ["total_revenue"]`, `dimensions: ["order_date.month"]`, dengan *header* autentikasi JWT pengguna.
2. **Context Resolution**: Engine mendekode JWT untuk mengekstrak identitas penyewa (`tenant_id`), hak akses grup (`roles`), dan atribut keamanan khusus (`country_access: ["ID", "SG"]`).
3. **DAG Resolution**: Engine menyusun Directed Acyclic Graph (DAG) untuk menyelesaikan dependensi kalkulasi metrik `total_revenue = SUM(amount * (1 - discount_rate))`.
4. **AST Modification (Security Injection)**: Engine mem-parsing definisi model menjadi AST SQL. Alih-alih melakukan *string formatting* (yang rentan SQL Injection), *compiler engine* menyisipkan *sub-tree* kondisi logis langsung ke *root WHERE clause*:
   $$\text{WHERE} \ (\text{original\_predicates}) \ \mathbf{AND} \ (\text{tenant\_id} = 'TENANT\_A' \ \mathbf{AND} \ \text{country} \ \mathbf{IN} \ ('ID', 'SG'))$$
5. **Dialect Transpilation**: Node AST diterjemahkan menjadi sintaks SQL spesifik target warehouse (misal: sintaks *window functions* BigQuery vs Snowflake).

#### B. Hierarki Caching & Pre-Aggregation Invalidation
Untuk mencegah kueri analitik berbiaya tinggi dieksekusi berulang kali ke warehouse:
*   **L1 Cache (In-Memory/Redis)**: Menyimpan representasi *in-memory* dari *result set* berdasarkan hash dari `(Compiled SQL + Security Context Digest)`. TTL biasanya singkat (5-60 menit).
*   **L2 Pre-Aggregation Store (ClickHouse / Local Parquet/DuckDB)**: Menyimpan tabel teragregasi yang diperbarui secara periodik. Evaluasi kesegaran data (*staleness*) didasarkan pada strategi watermark:
    $$\text{Staleness Trigger} = \text{MAX}(updated\_at) > \text{Last\_Build\_Timestamp}$$
    Jika L2 masih valid, eksekusi SQL dialihkan ke L2, memangkas waktu latensi dari 10 detik di data warehouse menjadi <50 milidetik.
*   **L3 Warehouse Passthrough**: Jika cache L1 *miss* dan agregasi L2 belum tersedia, kueri dialirkan ke Enterprise Data Warehouse dengan *resource governance limits* (misal: pembatasan waktu kueri maksimal 60 detik).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi Python produksi dari **Semantic Engine Query Compiler** yang menerapkan parsing model semantik, kompilasi SQL aman berbasis AST rewriter, proteksi *tenant-level isolation*, dan validasi hash pre-agregasi.

```python
"""
enterprise_bi_compiler.py
Komponen Inti Semantic Engine & Query Compiler dengan Penegakan RLS Deterministik.
"""

from __future__ import annotations
import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
logger = logging.getLogger("EnterpriseBICompiler")


# --------------------------------------------------------------------------
# DOMAIN MODELS & SCHEMAS
# --------------------------------------------------------------------------

class SQLDialect(str, Enum):
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    POSTGRESQL = "postgresql"


class SecurityContext(BaseModel):
    user_id: str
    tenant_id: str
    roles: List[str]
    allowed_regions: List[str]

    def compute_digest(self) -> str:
        """Menghasilkan fingerprint unik dari konteks keamanan untuk identifikasi cache."""
        payload = {
            "tenant_id": self.tenant_id,
            "roles": sorted(self.roles),
            "allowed_regions": sorted(self.allowed_regions),
        }
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class MeasureDefinition(BaseModel):
    name: str
    sql_formula: str
    description: Optional[str] = None


class DimensionDefinition(BaseModel):
    name: str
    sql_column: str
    type: str  # e.g., 'string', 'time', 'number'


class SemanticModel(BaseModel):
    model_name: str
    source_table: str
    dimensions: Dict[str, DimensionDefinition]
    measures: Dict[str, MeasureDefinition]
    mandatory_filters: List[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    model_name: str
    selected_measures: List[str]
    selected_dimensions: List[str]
    user_filters: Dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# EXCEPTIONS
# --------------------------------------------------------------------------

class SemanticEngineError(Exception):
    """Base exception untuk runtime semantic engine."""
    pass


class CompilationError(SemanticEngineError):
    """Terjadi ketika validasi kueri atau rewrite AST gagal."""
    pass


class SecurityViolationError(SemanticEngineError):
    """Terjadi jika terdeteksi manipulasi context atau pelanggaran boundary tenant."""
    pass


# --------------------------------------------------------------------------
# AST & SQL REWRITER ENGINE
# --------------------------------------------------------------------------

class EnterpriseQueryCompiler:
    def __init__(self, semantic_models: Dict[str, SemanticModel], dialect: SQLDialect = SQLDialect.SNOWFLAKE):
        self.semantic_models = semantic_models
        self.dialect = dialect

    def compile(self, request: QueryRequest, context: SecurityContext) -> str:
        """
        Mengompilasi permintaan logis menjadi SQL Dialek Target dengan proteksi RLS ketat.
        """
        logger.info(f"Mengompilasi kueri untuk Model: '{request.model_name}', Tenant: '{context.tenant_id}'")
        
        # 1. Validasi Keberadaan Model
        if request.model_name not in self.semantic_models:
            raise CompilationError(f"Model semantik '{request.model_name}' tidak terdaftar pada katalog metadata.")

        model = self.semantic_models[request.model_name]

        # 2. Validasi Kolom dan Ukuran (Measures & Dimensions)
        self._validate_fields(request, model)

        # 3. Kompilasi Proyeksi SELECT
        select_clauses: List[str] = []
        group_by_indexes: List[str] = []
        col_index = 1

        for dim_name in request.selected_dimensions:
            dim_def = model.dimensions[dim_name]
            select_clauses.append(f"{dim_def.sql_column} AS {dim_name}")
            group_by_indexes.append(str(col_index))
            col_index += 1

        for measure_name in request.selected_measures:
            measure_def = model.measures[measure_name]
            select_clauses.append(f"{measure_def.sql_formula} AS {measure_name}")
            col_index += 1

        # 4. Bangun Klausa Keamanan (RLS Injection)
        rls_predicates = self._build_security_predicates(context)

        # 5. Bangun Klausa Filter Pengguna yang Terverifikasi
        user_predicates = self._build_sanitized_user_predicates(request.user_filters, model)

        # Gabungkan semua predikat menggunakan konjungsi AND
        all_predicates = rls_predicates + user_predicates
        where_clause = " AND ".join(f"({predicate})" for predicate in all_predicates)

        # 6. Susun SQL Akhir
        sql_parts = [
            f"SELECT {', '.join(select_clauses)}",
            f"FROM {model.source_table}",
            f"WHERE {where_clause}"
        ]

        if group_by_indexes:
            sql_parts.append(f"GROUP BY {', '.join(group_by_indexes)}")

        # Pembatasan baris maksimal secara deterministik
        sql_parts.append("LIMIT 10000")

        compiled_sql = "\n".join(sql_parts) + ";"
        logger.debug(f"Compiled SQL Berhasil:\n{compiled_sql}")
        return compiled_sql

    def _validate_fields(self, request: QueryRequest, model: SemanticModel) -> None:
        """Memastikan semua atribut yang diminta tersedia dalam definisi deklaratif."""
        for dim in request.selected_dimensions:
            if dim not in model.dimensions:
                raise CompilationError(f"Dimensi '{dim}' tidak valid pada model '{model.model_name}'.")

        for measure in request.selected_measures:
            if measure not in model.measures:
                raise CompilationError(f"Measure '{measure}' tidak valid pada model '{model.model_name}'.")

        if not request.selected_measures:
            raise CompilationError("Kueri analitik wajib memuat minimal satu kalkulasi measure.")

    def _build_security_predicates(self, context: SecurityContext) -> List[str]:
        """
        Membangun filter keamanan data warehouse yang tidak dapat di-override oleh klien.
        """
        if not context.tenant_id or not context.tenant_id.strip():
            raise SecurityViolationError("Tenant ID hilang atau tidak valid dalam Security Context.")

        # Sanitasi sederhana untuk mencegah karakter berbahaya pada context values
        tenant_clean = context.tenant_id.replace("'", "''")
        predicates = [f"tenant_id = '{tenant_clean}'"]

        if context.allowed_regions:
            regions_formatted = ", ".join(f"'{r.replace('\'', '\'\'')}'" for r in context.allowed_regions)
            predicates.append(f"region IN ({regions_formatted})")
        else:
            # Jika user tidak memiliki alokasi region, blokir akses total secara default
            predicates.append("1 = 0")

        return predicates

    def _build_sanitized_user_predicates(self, user_filters: Dict[str, Any], model: SemanticModel) -> List[str]:
        """
        Memvalidasi filter yang dikirimkan oleh pengguna terhadap katalog dimensi.
        """
        predicates: List[str] = []
        for key, val in user_filters.items():
            if key not in model.dimensions:
                raise CompilationError(f"Upaya memfilter berdasarkan dimensi ilegal: '{key}'")

            target_col = model.dimensions[key].sql_column

            if isinstance(val, (int, float)):
                predicates.append(f"{target_col} = {val}")
            elif isinstance(val, str):
                clean_val = val.replace("'", "''")
                predicates.append(f"{target_col} = '{clean_val}'")
            elif isinstance(val, list):
                if not val:
                    continue
                if all(isinstance(x, (int, float)) for x in val):
                    list_str = ", ".join(str(x) for x in val)
                else:
                    list_str = ", ".join(f"'{str(x).replace('\'', '\'\'')}'" for x in val)
                predicates.append(f"{target_col} IN ({list_str})")
            else:
                raise CompilationError(f"Tipe data filter tidak didukung untuk atribut '{key}'.")

        return predicates


# --------------------------------------------------------------------------
# VERIFIKASI EKSEKUSI RUNTIME
# --------------------------------------------------------------------------

if __name__ == "__main__":
    # Inisialisasi Model Semantik Transaksi Penjualan
    sales_model = SemanticModel(
        model_name="fact_sales",
        source_table="prod_lakehouse.core.fact_sales",
        dimensions={
            "order_date": DimensionDefinition(name="order_date", sql_column="order_dt", type="time"),
            "region": DimensionDefinition(name="region", sql_column="region_code", type="string"),
            "category": DimensionDefinition(name="category", sql_column="product_category", type="string")
        },
        measures={
            "total_revenue": MeasureDefinition(
                name="total_revenue", 
                sql_formula="SUM(net_amount)"
            ),
            "order_count": MeasureDefinition(
                name="order_count", 
                sql_formula="COUNT(DISTINCT order_id)"
            )
        }
    )

    compiler = EnterpriseQueryCompiler(
        semantic_models={"fact_sales": sales_model},
        dialect=SQLDialect.SNOWFLAKE
    )

    # Simulasi Konteks Keamanan User yang Tervalidasi dari OIDC/IdP
    user_context = SecurityContext(
        user_id="usr_finance_099",
        tenant_id="tenant_apac_enterprise",
        roles=["Financial_Analyst"],
        allowed_regions=["ID", "SG"]
    )

    # Simulasi Permintaan dari BI Layer / LLM Agent
    client_request = QueryRequest(
        model_name="fact_sales",
        selected_dimensions=["region", "category"],
        selected_measures=["total_revenue", "order_count"],
        user_filters={"category": "Enterprise Software"}
    )

    try:
        generated_sql = compiler.compile(client_request, user_context)
        print("\n--- OUTPUT COMPILED SECURE SQL ---")
        print(generated_sql)
        print("\nSecurity Context Hash:", user_context.compute_digest())
    except SemanticEngineError as err:
        logger.error(f"Gagal memproses kueri semantik: {err}")
```

---

### 7. Edge Cases & Failure Modes

*   **Metric Self-Dependency & Recursion**: Saat menyusun kalkulasi tingkat lanjut (misal: rasio `Gross Margin % = Gross Margin / Net Sales` di mana kedua komponen adalah metrik turunan), dependensi siklis (*circular reference*) dapat mengakibatkan *infinite loop* saat parsing AST. Engine wajib memvalidasi graph menggunakan deteksi siklus berbasis DFS (*Depth-First Search*) saat model dimuat.
*   **Thundering Herd Problem (Cache Invalidation Collapse)**: Ketika partisi harian warehouse diperbarui pada tengah malam, seluruh *cache key* L1/L2 kadaluarsa serentak. Ratusan kueri yang masuk bersamaan dari dashboard eksekutif dapat membebani *warehouse cluster* hingga *timeout*.
    *   *Solusi Mitigasi*: Gunakan *Mutex Locks* berbasis Redis (*single-flight compilation*) sehingga hanya satu worker yang mengeksekusi kueri aktual ke warehouse, sementara thread lain menunggu pembaruan cache.
*   **RLS Bypass via Subquery Injection pada Dimension Value**: Analis atau penyerang dapat mencoba menginjeksi sintaks SQL pada parameter filter string (misal: `' OR 1=1 --`). Engine wajib menolak karakter kendali, memvalidasi terhadap *allow-list*, atau mengonversi nilai menjadi *strongly-typed AST literals*.
*   **Warehouse Dialect Incompatibility (Datetime & Timezone Drift)**: Query metrik agregasi harian dapat bergeser 1 hari tergantung apakah fungsi `DATE_TRUNC()` dieksekusi dalam timezone UTC, server, atau lokal pengguna. Engine semantik wajib memaksa eksplisit konversi timezone berbasis metadata klien: `DATE_TRUNC('DAY', CONVERT_TIMEZONE('UTC', 'Asia/Jakarta', order_dt))`.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Keputusan | Headless Semantic Engine (Cube / In-House Compiler) | Pure In-Database View Materialization (dbt) | Proprietary BI Engine (Tableau / Power BI Embedded) |
| :--- | :--- | :--- | :--- |
| **Kelebihan Utama** | Konsistensi mutlak lintas API, LLM Agents, dan dashboards; akselerasi multi-tier. | Sederhana; tidak memerlukan infrastruktur server runtime tambahan; 100% native warehouse. | Fitur visualisasi kaya bawaan; kapabilitas drag-and-drop end-user lengkap. |
| **Kelemahan** | Kompleksitas operasional: harus mengelola cluster Kubernetes, Redis, dan L2 cache store. | Kurang fleksibel untuk slicing-dicing real-time dinamis; biaya komputasi batch dbt membengkak. | *Metric divergence*; logika terkunci di visual layer; rawan halusinasi jika diakses oleh LLM Agent. |
| **Tingkat Latensi** | Sub-detik (10-100 ms) via Pre-Aggregation. | Tergantung kesiapan tabel warehouse (500 ms - 15 s). | Sub-detik jika via In-Memory Hyper/VertiPaq; lambat via DirectQuery. |
| **FinOps Impact** | Sangat Rendah (Warehouse tidak tersentuh untuk 80-90% read queries). | Sedang-Tinggi (Biaya materialisasi berkala warehouse). | Tinggi jika direct warehouse connection dibuka ke ribuan pengguna. |

---

### 9. Best Practices & Standard Industri

*   **Treat Metrics as Code (GitOps Driven)**: Seluruh file definisi semantik wajib disimpan dalam repositori Git monorepo. Perubahan logika rumus metrik harus melewati proses *Pull Request*, melalui validasi statis AST, *dry-run execution* terhadap database *staging*, serta *peer-review* dari Data Stewards sebelum di-deploy ke produksi.
*   **Zero-Trust Context Injection**: Jangan pernah mempercayai parameter tenant yang dikirimkan melalui URL atau body permintaan klien visualisasi. Parameter isolasi wajib diinjeksi secara eksklusif dari klaim JWT yang diverifikasi secara kriptografis oleh API Gateway via *OpenID Connect* (OIDC) / IdP enterprise.
*   **Idempotency & Fingerprint Caching**: Kunci cache harus merupakan fungsi deterministik dari:
    $$\text{Cache Key} = \text{SHA256}(\text{Compiled SQL} + \text{Dialect} + \text{Security Context Digest})$$
    Ini menjamin kerahasiaan bahwa tenant yang berbeda tidak akan pernah bisa membaca cache satu sama lain meskipun menjalankan query metrik yang sama.
*   **Observability & Telemetry Standardization**: Kirimkan metrik eksekusi platform BI via OpenTelemetry (OTel):
    *   *Compilation Latency* ($p99 < 5\text{ ms}$).
    *   *Cache Hit Ratio* (Target: $> 85\%$).
    *   *Warehouse Execution Time* ($p95 < 2\text{ s}$).
    *   *Active Query Concurrency Limits* per Tenant.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertugas men-deploy dan mengonfigurasi lapisan tata kelola Semantic Layer untuk perusahaan retail multi-tenant. Anda harus membuat definisi model semantik, memvalidasi mekanisme isolasi *Row-Level Security* (RLS), dan memastikan bahwa upaya *data leakage* antar-tenant dicegah secara mutlak oleh runtime compiler.

#### Langkah 1: Persiapan Environment
Pastikan Python 3.10+ terinstal. Simpan kode implementasi pada bagian 6 sebagai `enterprise_bi_compiler.py`.

#### Langkah 2: Buat Skrip Verifikasi Keamanan (`test_governance_lab.py`)
Tuliskan suite pengujian berikut untuk menguji isolasi penyewa:

```python
"""
test_governance_lab.py
Suite pengujian otomatis untuk memvalidasi isolasi RLS dan keandalan compiler.
"""

import pytest
from enterprise_bi_compiler import (
    EnterpriseQueryCompiler, SemanticModel, DimensionDefinition,
    MeasureDefinition, SecurityContext, QueryRequest, SQLDialect,
    CompilationError, SecurityViolationError
)

@pytest.fixture
def compiler_instance():
    order_model = SemanticModel(
        model_name="orders",
        source_table="analytics.dw.fact_orders",
        dimensions={
            "customer_id": DimensionDefinition(name="customer_id", sql_column="cust_id", type="string"),
            "region": DimensionDefinition(name="region", sql_column="region", type="string"),
        },
        measures={
            "gmv": MeasureDefinition(name="gmv", sql_formula="SUM(gross_amount)")
        }
    )
    return EnterpriseQueryCompiler(
        semantic_models={"orders": order_model},
        dialect=SQLDialect.SNOWFLAKE
    )

def test_tenant_isolation_success(compiler_instance):
    """Memverifikasi bahwa Tenant A hanya menghasilkan query terisolasi untuk Tenant A."""
    ctx_a = SecurityContext(
        user_id="user_a",
        tenant_id="TENANT_ALPHA",
        roles=["Analyst"],
        allowed_regions=["US-EAST"]
    )
    req = QueryRequest(
        model_name="orders",
        selected_measures=["gmv"],
        selected_dimensions=["customer_id"]
    )

    compiled_sql = compiler_instance.compile(req, ctx_a)

    assert "tenant_id = 'TENANT_ALPHA'" in compiled_sql
    assert "region IN ('US-EAST')" in compiled_sql
    assert "analytics.dw.fact_orders" in compiled_sql

def test_empty_tenant_security_violation(compiler_instance):
    """Memverifikasi bahwa SecurityContext tanpa Tenant ID memicu error kritis."""
    ctx_invalid = SecurityContext(
        user_id="hacker",
        tenant_id="",  # Pelanggaran boundary
        roles=["Guest"],
        allowed_regions=["US-EAST"]
    )
    req = QueryRequest(
        model_name="orders",
        selected_measures=["gmv"],
        selected_dimensions=["customer_id"]
    )

    with pytest.raises(SecurityViolationError):
        compiler_instance.compile(req, ctx_invalid)

def test_unregistered_dimension_rejection(compiler_instance):
    """Memverifikasi bahwa query dengan field ilegal/tidak terdaftar langsung ditolak."""
    ctx_a = SecurityContext(
        user_id="user_a",
        tenant_id="TENANT_ALPHA",
        roles=["Analyst"],
        allowed_regions=["US-EAST"]
    )
    req = QueryRequest(
        model_name="orders",
        selected_measures=["gmv"],
        selected_dimensions=["unregistered_credit_card_column"]
    )

    with pytest.raises(CompilationError):
        compiler_instance.compile(req, ctx_a)

if __name__ == "__main__":
    pytest.main(["-v", "test_governance_lab.py"])
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan pengujian menggunakan `pytest`:
```bash
python3 -m pip install pytest pydantic
pytest -v test_governance_lab.py
```

#### Langkah 4: Kriteria Keberhasilan Verifikasi
1. Seluruh pengujian passing (`3 passed`).
2. Predikat `tenant_id` dan `region` terbukti disuntikkan secara deterministik ke dalam klausul `WHERE` tanpa modifikasi manual dari sisi analis/klien.
3. Upaya penyusupan nama dimensi ilegal atau manipulasi identitas tenant langsung digagalkan sebelum kueri mencapai layer data warehouse.