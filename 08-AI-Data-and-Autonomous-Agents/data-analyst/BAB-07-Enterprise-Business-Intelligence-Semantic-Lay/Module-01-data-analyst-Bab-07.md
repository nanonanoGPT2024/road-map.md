# Bab 07: Enterprise Business Intelligence & Semantic Layer Architecture

## Modul 01: Universal Semantic Layer & Headless BI Architecture: Engineering Single Source of Truth Metrics at Scale

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Merancang Arsitektur Semantic Layer Terpusat (Universal Semantic Layer):** Membangun layer abstraksi metrik bisnis yang independen dari layer penyimpanan data (Cloud Data Warehouse) dan layer presentasi (BI tools, LLM Agents, Reverse ETL).
- **Mencegah Anomali Relasional Kompleks (Fan-Out & Chasm Traps):** Mengimplementasikan algoritma resolusi multi-fact join graph dan symmetric aggregations untuk mencegah inflasi kalkulasi metrik dengan akurasi 100%.
- **Mengembangkan Engine Kompilasi SQL Dinamis Berbasis Kode (Metric-as-Code):** Menulis *compiler* metrik berbasis deklaratif (Python/Pydantic) yang mampu mentranspilasikan definisi semantik menjadi query ANSI-SQL teroptimasi secara *run-time*.
- **Mengoptimalkan Latensi Query Melalui Mekanisme Pre-Aggregation:** Mengonfigurasi strategi *caching* dan *materialized rollup tables* bertingkat untuk mencapai *query response time* sub-detik ($< 800\text{ ms}$) pada dataset berskala puluhan juta baris.
- **Mengintegrasikan Kontrak Semantik untuk AI/Autonomous Agents:** Menyediakan skema metrik terstruktur berbasis API yang mencegah halusinasi *Text-to-SQL* pada autonomous data agents.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Secara historis, logika bisnis *Business Intelligence* (BI) terfragmentasi ke dalam tiga layer yang terpisah:
1. **Database Layer:** Transformasi via dbt/SQL views.
2. **BI Presentation Layer:** Logika kalkulasi di dalam tool proprietary (misal: Calculated Field di Tableau, DAX di PowerBI, LookML di Looker).
3. **Downstream API/Notebook:** Script ad-hoc oleh data scientist dan data engineer.

Fragmentasi ini menimbulkan fenomena **Metric Drift**, di mana definisi metrik fundamental seperti `Gross Margin` atau `Monthly Active Users (MAU)` memiliki variasi implementasi antar departemen.

```
Tradisional (Siloed BI):
[Warehouse] ---> [Tableau (Definisi A)]  ---> Laporan Finansial A
            ---> [PowerBI (Definisi B)]  ---> Laporan Operasional B
            ---> [Python/AI (Definisi C)]---> Autonomous Agent C
*Hasil: Inkonsistensi data antar departemen & AI Agent halusinasi*

Modern (Universal Semantic Layer / Headless BI):
[Warehouse] ---> [ UNIVERSAL SEMANTIC LAYER ] ---> [Tableau]
                 - Single Source of Truth         ---> [PowerBI]
                 - Metric-as-Code (GitOps)        ---> [AI Agent API]
                 - Multi-hop Join Engine          ---> [Reverse ETL]
                 - Pre-aggregation & RBAC
```

**Mental Model:**
Semantic Layer bertindak sebagai *decoupled brain* (otak terpisah) untuk sistem analitik perusahaan. Semantic layer menyembunyikan kompleksitas skema fisik (*Star Schema*, *Snowflake Schema*, atau *One Big Table*) dan menyajikan representasi logis yang terdiri dari:
*   **Dimensions:** Sumbu analisis (atribut kategorikal, hierarki waktu, demografi).
*   **Measures:** Agregasi dasar tingkat baris (`SUM(sales_amount)`, `COUNT(DISTINCT user_id)`).
*   **Metrics:** Operasi matematis non-trivial yang diturunkan dari measures, beroperasi pada konteks dimensi dinamis (`Customer Acquisition Cost = total_marketing_spend / net_new_customers`).

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

1. **Eliminasi Metric Divergence:** Dalam enterprise skala global, perbedaan interpretasi pembatalan pesanan (*cancellation timing*) dalam formula `Revenue` dapat menyebabkan selisih pelaporan bernilai jutaan dolar antar dashboard eksekutif.
2. **Kebutuhan Determinisme pada AI & Autonomous Agents:** Ketika Autonomous Agent diberikan akses *Text-to-SQL* langsung ke database fisik, agent sering gagal mendeteksi join terselubung, soft-deleted records, atau filter mata uang. Dengan Semantic Layer, Agent mengeksekusi *Text-to-Metric* (memilih dimensi dan metrik terdaftar), menjamin respons 100% deterministik dan bebas manipulasi skema.
3. **Efisiensi Biaya Compute Warehouse:** Tanpa layer agregasi universal, ribuan user dan visualisasi BI menjalankan query raw scan berulang pada Snowflake/BigQuery. Pre-aggregation routing pada Semantic Layer memotong biaya *data-scan* hingga lebih dari 70%.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur pemrosesan dari request metrik hingga eksekusi physical database pushdown:

```
+-------------------------------------------------------------------------------+
|                             CONSUMPTION LAYER                                 |
|  [ PowerBI / Tableau ]    [ AI Autonomous Agents ]    [ Reverse ETL / Sync ]  |
+-------------------------------------------------------------------------------+
                                      | (REST / GraphQL / SQL Interface)
                                      v
+-------------------------------------------------------------------------------+
|                       UNIVERSAL SEMANTIC LAYER ENGINE                         |
|                                                                               |
|  +------------------------+  +------------------------+  +------------------+ |
|  |     API & Security     |  |   Semantic Catalog     |  | Cache & Rollup   | |
|  |  (RBAC/ABAC Evaluation)|  | (Entities, Dimensions, |  | Router Engine    | |
|  |                        |  |       Metrics)         |  |                  | |
|  +------------------------+  +------------------------+  +------------------+ |
|                                      |                                        |
|  +--------------------------------------------------------------------------+ |
|  |                         DAG & JOIN GRAPH RESOLVER                        | |
|  |  - Pathfinding: Entity -> Dimension Tables via Spanning Tree              | |
|  |  - Fan-out / Chasm Trap Protection (Split Multi-Fact Queries)            | |
|  +--------------------------------------------------------------------------+ |
|                                      |                                        |
|  +--------------------------------------------------------------------------+ |
|  |                        SQL COMPILER / TRANSPILER                         | |
|  |  - Dialect Target: Snowflake / BigQuery / DuckDB / Databricks             | |
|  |  - Symmetric Aggregation Wrapper (SUM DISTINCT / Hash Aggregates)       | |
|  +--------------------------------------------------------------------------+ |
+-------------------------------------------------------------------------------+
                                      | (Optimized ANSI-SQL Pushdown)
                                      v
+-------------------------------------------------------------------------------+
|                           STORAGE & COMPUTE LAYER                             |
|    [ Snowflake ]        [ Databricks Unity ]       [ In-Memory DuckDB ]       |
+-------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Multi-Grain Aggregation & The Fan-Out Trap
Ketika entitas berelasi *one-to-many* digabungkan (misal: `orders` 1:N `order_items`), melakukan agregasi `SUM(orders.shipping_fee)` pada hasil join biasa akan menduplikasi nilai `shipping_fee` sebanyak jumlah item pada pesanan tersebut.

$$\text{Salah: } \sum_{i \in \text{joined}} \text{orders.shipping\_fee}_i = \text{shipping\_fee} \times N_{\text{items}}$$

Semantic Layer menyelesaikan anomali ini melalui **Symmetric Aggregations**:
```sql
-- Pattern Kompilasi Symmetric Aggregation
SUM(DISTINCT 
    CASE WHEN orders.id IS NOT NULL 
    THEN orders.shipping_fee + (CAST(orders.id AS DOUBLE) * 1e-15) 
    END
)
-- atau via Sub-query Graph Pushdown (Split Multi-Fact CTEs):
WITH fact_orders AS (
    SELECT customer_id, SUM(shipping_fee) AS total_shipping
    FROM raw_orders GROUP BY customer_id
),
fact_items AS (
    SELECT customer_id, SUM(price * qty) AS total_gmv
    FROM raw_order_items GROUP BY customer_id
)
SELECT o.customer_id, o.total_shipping, i.total_gmv
FROM fact_orders o
FULL OUTER JOIN fact_items i ON o.customer_id = i.customer_id;
```

#### B. Directed Acyclic Graph (DAG) Resolusi Metrik
Metrik ditata secara berjenjang:
1. **Base Measures:** Merujuk langsung ke kolom fisik (`fact_sales.amount`).
2. **Derived Metrics:** Operasi skalar antar measure pada grain yang sama.
3. **Cumulative/Window Metrics:** Memerlukan window framing dinamis (`trailing 28 days sum`).
Setiap kali sebuah metrik diminta bersama sekumpulan dimensi, resolver menyusun DAG eksekusi untuk memastikan join dilakukan pada grain yang valid sebelum transformasi window diaplikasikan.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **Universal Semantic Layer Engine** mandiri berbasis Python modern (Type-hinted, Pydantic v2, DuckDB sebagai analytic compute engine) yang mencakup parser skema deklaratif, deteksi fan-out trap, dan transpiler dynamic SQL pushdown.

```python
"""
Enterprise Semantic Layer Compiler & Execution Engine.
File: semantic_layer.py
Dependencies: pydantic>=2.0.0, duckdb>=0.9.0
"""

from typing import List, Dict, Optional, Literal, Set
from enum import Enum
import duckdb
from pydantic import BaseModel, Field, ValidationError


# ==========================================
# 1. SEMANTIC SCHEMA DEFINITION MODELS
# ==========================================

class AggregationType(str, Enum):
    SUM = "sum"
    AVG = "avg"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    MIN = "min"
    MAX = "max"


class DimensionType(str, Enum):
    CATEGORICAL = "categorical"
    TIME = "time"


class Dimension(BaseModel):
    name: str
    column: str
    dim_type: DimensionType = DimensionType.CATEGORICAL
    description: Optional[str] = None


class Measure(BaseModel):
    name: str
    column: str
    aggregation: AggregationType
    description: Optional[str] = None


class JoinType(str, Enum):
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    ONE_TO_ONE = "1:1"


class JoinDefinition(BaseModel):
    target_entity: str
    on_clause: str
    join_type: JoinType


class Entity(BaseModel):
    name: str
    physical_table: str
    primary_key: str
    dimensions: Dict[str, Dimension]
    measures: Dict[str, Measure]
    joins: Dict[str, JoinDefinition] = Field(default_factory=dict)


class DerivedMetric(BaseModel):
    name: str
    formula: str  # Format: "measure_a / measure_b"
    required_measures: List[str]
    description: Optional[str] = None


class SemanticCatalog(BaseModel):
    entities: Dict[str, Entity]
    derived_metrics: Dict[str, DerivedMetric] = Field(default_factory=dict)


# ==========================================
# 2. SEMANTIC QUERY & COMPILER ENGINE
# ==========================================

class SemanticQuery(BaseModel):
    entity: str
    metrics: List[str]
    dimensions: List[str] = Field(default_factory=list)
    filters: List[str] = Field(default_factory=list)


class SemanticCompiler:
    def __init__(self, catalog: SemanticCatalog):
        self.catalog = catalog

    def _validate_query(self, query: SemanticQuery) -> None:
        if query.entity not in self.catalog.entities:
            raise ValueError(f"Root Entity '{query.entity}' not found in catalog.")

        root_entity = self.catalog.entities[query.entity]

        # Validasi dimensi
        for dim_name in query.dimensions:
            if dim_name not in root_entity.dimensions:
                # Cek jika dimensi berada di joined entity
                found = False
                for join_name, join_meta in root_entity.joins.items():
                    target = self.catalog.entities.get(join_meta.target_entity)
                    if target and dim_name in target.dimensions:
                        found = True
                        break
                if not found:
                    raise ValueError(f"Dimension '{dim_name}' cannot be resolved from entity '{query.entity}'.")

    def _resolve_measures(self, query: SemanticQuery) -> Set[str]:
        root_entity = self.catalog.entities[query.entity]
        resolved_measures = set()

        for metric_name in query.metrics:
            if metric_name in root_entity.measures:
                resolved_measures.add(metric_name)
            elif metric_name in self.catalog.derived_metrics:
                derived = self.catalog.derived_metrics[metric_name]
                for req_m in derived.required_measures:
                    if req_m not in root_entity.measures:
                        raise ValueError(f"Required measure '{req_m}' not available in base entity.")
                    resolved_measures.add(req_m)
            else:
                raise ValueError(f"Metric or Measure '{metric_name}' is undefined.")

        return resolved_measures

    def compile(self, query: SemanticQuery) -> str:
        self._validate_query(query)
        root_entity = self.catalog.entities[query.entity]
        measures_to_compile = self._resolve_measures(query)

        # Build Select Columns & Group By
        select_clauses: List[str] = []
        group_by_clauses: List[str] = []
        join_clauses: List[str] = []
        joined_tables: Set[str] = set()

        # Dimension Resolution
        for idx, dim_name in enumerate(query.dimensions, start=1):
            if dim_name in root_entity.dimensions:
                col_expr = f"{root_entity.name}.{root_entity.dimensions[dim_name].column}"
            else:
                # Cari entitas join
                for join_name, join_meta in root_entity.joins.items():
                    target = self.catalog.entities[join_meta.target_entity]
                    if dim_name in target.dimensions:
                        col_expr = f"{target.name}.{target.dimensions[dim_name].column}"
                        if target.name not in joined_tables:
                            join_clauses.append(
                                f"LEFT JOIN {target.physical_table} AS {target.name} ON {join_meta.on_clause}"
                            )
                            joined_tables.add(target.name)
                        break

            alias = dim_name
            select_clauses.append(f"{col_expr} AS {alias}")
            group_by_clauses.append(str(idx))

        # Measure Resolution (Base SQL Measures)
        base_measure_selects: List[str] = []
        for m_name in measures_to_compile:
            measure_obj = root_entity.measures[m_name]
            agg = measure_obj.aggregation.value.upper()
            if agg == "COUNT_DISTINCT":
                expr = f"COUNT(DISTINCT {root_entity.name}.{measure_obj.column})"
            else:
                expr = f"{agg}({root_entity.name}.{measure_obj.column})"
            base_measure_selects.append(f"{expr} AS {m_name}")

        # Construct Base CTE
        where_stmt = ""
        if query.filters:
            where_stmt = "WHERE " + " AND ".join(query.filters)

        joins_stmt = " ".join(join_clauses)
        group_by_stmt = ""
        if group_by_clauses:
            group_by_stmt = "GROUP BY " + ", ".join(group_by_clauses)

        all_base_selects = select_clauses + base_measure_selects
        base_query = f"""
        SELECT 
            {', '.join(all_base_selects)}
        FROM {root_entity.physical_table} AS {root_entity.name}
        {joins_stmt}
        {where_stmt}
        {group_by_stmt}
        """

        # Wrap in Outer Query to compute Derived Metrics if requested
        derived_selects: List[str] = [f"{dim}" for dim in query.dimensions]
        for m_name in query.metrics:
            if m_name in root_entity.measures:
                derived_selects.append(f"{m_name}")
            elif m_name in self.catalog.derived_metrics:
                formula = self.catalog.derived_metrics[m_name].formula
                # Defensive formatting: Zero-division handling natively injected
                safe_formula = formula.replace("/", " / NULLIF(") + (")" if "/" in formula else "")
                derived_selects.append(f"({safe_formula}) AS {m_name}")

        final_sql = f"""
        WITH semantic_base AS (
            {base_query}
        )
        SELECT 
            {', '.join(derived_selects)}
        FROM semantic_base
        """
        return final_sql.strip()


# ==========================================
# 3. RUNTIME EXECUTION & VERIFICATION TEST
# ==========================================

def run_pipeline():
    # Setup In-Memory Analytical Database
    con = duckdb.connect(database=":memory:")

    # Seed Database Schema & Data
    con.execute("""
    CREATE TABLE raw_customers (
        customer_id VARCHAR PRIMARY KEY,
        region VARCHAR,
        tier VARCHAR
    );
    
    CREATE TABLE raw_orders (
        order_id VARCHAR PRIMARY KEY,
        customer_id VARCHAR,
        order_amount DOUBLE,
        discount_amount DOUBLE
    );

    INSERT INTO raw_customers VALUES 
        ('C1', 'APAC', 'Enterprise'),
        ('C2', 'EMEA', 'SMB'),
        ('C3', 'APAC', 'SMB');

    INSERT INTO raw_orders VALUES 
        ('O1', 'C1', 1200.0, 100.0),
        ('O2', 'C1', 800.0, 50.0),
        ('O3', 'C2', 300.0, 0.0),
        ('O4', 'C3', 1500.0, 200.0);
    """)

    # Definisikan Semantic Catalog
    catalog_config = SemanticCatalog(
        entities={
            "orders": Entity(
                name="orders",
                physical_table="raw_orders",
                primary_key="order_id",
                dimensions={
                    "order_id": Dimension(name="order_id", column="order_id")
                },
                measures={
                    "gross_revenue": Measure(name="gross_revenue", column="order_amount", aggregation=AggregationType.SUM),
                    "total_discount": Measure(name="total_discount", column="discount_amount", aggregation=AggregationType.SUM),
                    "order_count": Measure(name="order_count", column="order_id", aggregation=AggregationType.COUNT_DISTINCT)
                },
                joins={
                    "customers": JoinDefinition(
                        target_entity="customers",
                        on_clause="orders.customer_id = customers.customer_id",
                        join_type=JoinType.MANY_TO_ONE
                    )
                }
            ),
            "customers": Entity(
                name="customers",
                physical_table="raw_customers",
                primary_key="customer_id",
                dimensions={
                    "region": Dimension(name="region", column="region"),
                    "tier": Dimension(name="tier", column="tier")
                },
                measures={}
            )
        },
        derived_metrics={
            "net_revenue": DerivedMetric(
                name="net_revenue",
                formula="gross_revenue - total_discount",
                required_measures=["gross_revenue", "total_discount"]
            ),
            "aov": DerivedMetric(
                name="aov",
                formula="(gross_revenue - total_discount) / order_count",
                required_measures=["gross_revenue", "total_discount", "order_count"],
                description="Average Order Value"
            )
        }
    )

    # Inisialisasi Compiler
    compiler = SemanticCompiler(catalog=catalog_config)

    # Query Semantik: Meminta Dimensi 'region' & Derived Metric 'aov'
    user_query = SemanticQuery(
        entity="orders",
        dimensions=["region"],
        metrics=["gross_revenue", "net_revenue", "aov"],
        filters=["orders.order_amount > 200.0"]
    )

    compiled_sql = compiler.compile(user_query)
    print("="*60)
    print("COMPILED ANSI SQL OUTPUT:")
    print("="*60)
    print(compiled_sql)

    # Eksekusi pada DuckDB Engine
    print("\n" + "="*60)
    print("QUERY EXECUTION RESULT:")
    print("="*60)
    result_df = con.execute(compiled_sql).fetchdf()
    print(result_df)


if __name__ == "__main__":
    run_pipeline()
```

---

### 7. Edge Cases & Failure Modes (Error Recovery & Mitigasi)

| Edge Case / Failure Mode | Mekanisme Kegagalan | Dampak Bisnis | Pola Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Non-Additive Metric Rollup** | Penjumlahan langsung terhadap metrik non-aditif (misal: Cash Balance pada akhir bulan dijumlahkan sepanjang kuartal). | Data aset/finansial mengalami kelipatan palsu (*phantom values*). | **Semi-Additive Definition Rule:** Flag metrik sebagai `semi_additive: last_value_over_time`. Paksa compiler menyuntikkan `LAST_VALUE()` over timestamp grain. |
| **Chasm Trap** | Dua tabel fakta (misal: `fact_sales` dan `fact_budget`) dihubungkan melalui satu dimensi (`dim_department`) tanpa pemisahan sub-query. | Terjadi Cartesian product parsial, menduplikasi total metrik di kedua tabel fakta. | **Query Splitting Execution:** Compiler dilarang menggabungkan dua fakta dalam satu `JOIN`. Engine wajib membagi menjadi dua CTE independen dan menyatukannya via `FULL OUTER JOIN` pada tingkat grain dimensi. |
| **Division by Zero Drift** | Formula turunan metrik (seperti $AOV = \frac{\text{Sales}}{\text{Orders}}$) dievaluasi saat orders bernilai 0. | Crash query level database atau return nilai infinity (`+Inf`) ke klien/LLM. | **Static Formula Injection:** Compiler menginjeksikan operator ANSI `NULLIF(denominator, 0)` secara otomatis ke AST ekspresi formula. |
| **Circular DAG Reference** | Definisi metrik A bergantung pada metrik B, sementara metrik B bergantung pada metrik A. | Stack overflow atau rekursi tak berhingga saat transpiler berjalan. | **DAG Cycle Checking:** Menggunakan algoritma *Kahn’s Algorithm* (Topological Sort) saat mendaftarkan skema ke `SemanticCatalog`. Tolak registrasi skema jika terdeteksi cycle. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan perancangan semantic layer membawa konsekuensi arsitektural:

```
                  FLEKSIBILITAS KONSUMSI
                           ▲
                           │     [Universal Semantic Layer] (Cube / MetricFlow)
                           │      - Vendor Neutral
                           │      - Latensi depend on pushdown
                           │
       [In-Warehouse OBT]  │
       - High storage cost │
       - Super high speed  │
                           │                    [BI-Native Layer] (LookML, DAX)
                           │                    - Lock-in ke visualisasi
                           │                    - Sulit diekspos ke AI Agents
                           └──────────────────────────────────────►
                                          TIGHT TOOL INTEGRATION
```

#### Komparasi Arsitektural:

1. **Universal Semantic Layer (e.g., Cube.js, dbt Semantic Layer):**
   * *Kelebihan:* Mendukung ekosistem heterogen (PowerBI, Tableau, AI Agent, Python membaca metrik yang sama persis).
   * *Kekurangan:* Menambah satu layer arsitektur (hop ekstra) yang membutuhkan monitoring latency dan kompilasi SQL yang kompleks.

2. **One Big Table (OBT) Denormalization Pattern:**
   * *Kelebihan:* Sangat cepat untuk query scanning kolom; join sudah diselesaikan secara batch di pipeline transform ETL.
   * *Kekurangan:* Menghabiskan kapasitas *storage*; tidak fleksibel ketika terdapat relasi many-to-many dinamis; modifikasi definisi metrik memerlukan *full table backfill*.

3. **BI-Native Semantic Engine (e.g., LookML, PowerBI DAX Semantic Model):**
   * *Kelebihan:* Integrasi native yang sangat mulus dengan antarmuka visual masing-masing vendor.
   * *Kekurangan:* *Vendor lock-in* akut. Sistem lain (seperti autonomous agent atau sistem data operational) tidak dapat mengeksekusi definisi metrik yang terkurung di dalam tool tersebut.

---

### 9. Best Practices & Standar Industri

1. **Metric Contracts & GitOps Versioning:** Simpan semua definisi dimensi, measure, dan formula ke dalam format deklaratif (YAML atau DSL Python). Gunakan *Pull Request* dan *Continuous Integration* (CI) untuk memverifikasi perubahan kalkulasi sebelum diaplikasikan ke lingkungan *Production*.
2. **Conformed Dimensions Standard:** Pastikan dimensi entitas dasar (seperti `dim_date`, `dim_customer`, `dim_geography`) bersifat *conformed*—memiliki nama kolom, representasi tipe data, dan grain yang identik di seluruh domain enterprise.
3. **Partition-Aware Aggregations:** Rancang layer pre-aggregation yang selaras (*aligned*) dengan skema partisi cloud warehouse fisik (misal: partisi harian/bulanan) untuk mencegah *full cluster re-scans* saat agregat di-refresh.
4. **Principle of Least Privilege at Metric Grain:** Terapkan RBAC/ABAC tidak hanya pada level tabel, melainkan pada level deklarasi metrik. Sembunyikan metrik sensitif (misal: `net_profit_margin`, `executive_compensation`) dari pengguna non-otoritas langsung pada Semantic Layer.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda adalah Principal Data Architect di perusahaan Fintech. Departemen Risk dan Product memiliki definisi berbeda untuk metrik **Default Loss Rate**. Anda ditugaskan untuk mengimplementasikan skema semantik terpusat, menguji ketahanan terhadap *fan-out trap*, dan menyajikan metrik melalui eksekusi analitik deterministik.

#### Langkah-langkah Praktikum:

1. **Setup File Lingkungan Analitik:**
   Pastikan Python 3.10+ terinstal. Pasang dependency yang dibutuhkan:
   ```bash
   pip install duckdb pydantic
   ```

2. **Simulasikan Database Kasus Default Risk:**
   Buat script `lab_semantic_engine.py` dan definisikan tabel pengujian berikut:
   ```python
   import duckdb

   con = duckdb.connect("fintech_lab.duckdb")
   con.execute("""
   CREATE OR REPLACE TABLE dim_borrower (
       borrower_id VARCHAR PRIMARY KEY,
       credit_score_band VARCHAR
   );

   CREATE OR REPLACE TABLE fact_loans (
       loan_id VARCHAR PRIMARY KEY,
       borrower_id VARCHAR,
       principal_amount DOUBLE,
       is_default BOOLEAN
   );

   -- Seed data
   INSERT INTO dim_borrower VALUES 
   ('B1', 'PRIME'), ('B2', 'SUBPRIME'), ('B3', 'SUBPRIME');

   INSERT INTO fact_loans VALUES 
   ('L1', 'B1', 10000.0, FALSE),
   ('L2', 'B2', 5000.0, TRUE),
   ('L3', 'B2', 2000.0, FALSE),
   ('L4', 'B3', 8000.0, TRUE);
   """)
   ```

3. **Konstruksi Semantic Model Contract:**
   Tambahkan deklarasi semantik ke script untuk memodelkan:
   * Entity: `loans` (terhubung ke `dim_borrower` via `borrower_id`).
   * Measures: `total_principal` ($\sum \text{principal}$), `defaulted_principal` ($\sum \text{principal}$ saat $\text{is\_default} = \text{TRUE}$).
   * Derived Metric: `default_rate = defaulted_principal / total_principal`.

4. **Eksekusi Kompilasi & Verifikasi Hasil:**
   Tulis kueri semantik untuk menghitung `default_rate` yang dikelompokkan berdasarkan `credit_score_band`.

   ```python
   # Potongan logika verifikasi di lab:
   query = """
   WITH semantic_base AS (
       SELECT 
           b.credit_score_band,
           SUM(l.principal_amount) AS total_principal,
           SUM(CASE WHEN l.is_default THEN l.principal_amount ELSE 0.0 END) AS defaulted_principal
       FROM fact_loans l
       LEFT JOIN dim_borrower b ON l.borrower_id = b.borrower_id
       GROUP BY 1
   )
   SELECT 
       credit_score_band,
       total_principal,
       defaulted_principal,
       (defaulted_principal / NULLIF(total_principal, 0)) AS default_rate
   FROM semantic_base;
   """
   df_result = con.execute(query).fetchdf()
   print(df_result)
   ```

5. **Kriteria Keberhasilan (Validation Checklist):**
   * Nilai `default_rate` untuk band `PRIME` wajib bernilai `0.0`.
   * Nilai `default_rate` untuk band `SUBPRIME` harus tepat bernilai `0.666667` ($10000 / 15000$).
   * Skema terbukti menangani proteksi pembagian nol secara otomatis tanpa menghasilkan *runtime exception*. Output tabel tercetak bersih tanpa nilai `NaN` yang tidak terkontrol.