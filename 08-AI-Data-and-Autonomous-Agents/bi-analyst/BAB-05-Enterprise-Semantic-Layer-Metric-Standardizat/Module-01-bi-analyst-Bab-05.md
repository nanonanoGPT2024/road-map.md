# Bab 05: Enterprise Semantic Layer & Metric Standardization
## Modul 01: Arsitektur Fundamental Semantic Layer & Standardisasi Metrik Deklaratif

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Mengidentifikasi Anomali Semantik (Metric Drift):** Menemukan inkonsistensi kalkulasi metrik finansial dan operasional lintas platform BI (*Business Intelligence*) dengan membedah dependensi *grain* dan relasi data warehouse.
2. **Merancang Model Metrik Deklaratif Berbasis Kode (Metrics-as-Code):** Mengonstruksi spesifikasi semantik formal menggunakan model YAML/Pydantic yang memisahkan definisi logika bisnis secara tegas dari lapisan penyimpanan fisik (*physical storage layer*).
3. **Mengatasi Jebakan Relasional Kompleks (*Chasm Trap* & *Fan-Out Trap*):** Mengimplementasikan algoritma resolusi jalur *join* (*join-path resolution*) otomatis untuk mencegah duplikasi agregasi metrik saat menghubungkan beberapa tabel fakta (*fact tables*) dengan dimensi bersama (*conformed dimensions*).
4. **Membangun Kompilator Kueri Semantik Dinamis:** Mengembangkan mesin translasi (*query translation engine*) berbasis Python yang mengonversi definisi metrik deklaratif menjadi kueri SQL teroptimasi (misal: Dialek DuckDB/Snowflake/BigQuery) secara deterministik.
5. **Menyediakan Antarmuka Terpadu untuk Konsumsi Multimodal:** Mengintegrasikan *semantic layer* dengan *autonomous data agent* (LLM) melalui API semantik yang tervalidasi skema guna mengeliminasi halusinasi definisi kalkulasi metrik.

---

### 2. Concept Overview

*Enterprise Semantic Layer* adalah lapisan abstraksi terpusat yang memformalkan logika bisnis, hierarki dimensi, relasi entitas, dan kalkulasi metrik di atas gudang data (*data warehouse* atau *data lakehouse*). Lapisan ini berdiri independen dari visualisasi data (seperti Tableau, PowerBI, Metabase) maupun antarmuka kueri hilir (seperti AI Agent dan notebook analitik).

```
[ Traditional Anti-Pattern: Logic Sprawl ]
Physical Tables ---> Tableau (Revenue Logic A)
                ---> PowerBI (Revenue Logic B)
                ---> Python/Agent (Revenue Logic C)

[ Modern Semantic Architecture: Single Point of Truth ]
Physical Tables ---> [ Enterprise Semantic Layer ] ---> Tableau
                                                  ---> PowerBI
                                                  ---> LLM / Autonomous Agent
```

#### Mental Model: Pemisahan State, Logic, dan Presentation

Untuk memahami *semantic layer*, gunakan mental model **Tiga Tingkat Abstraksi Analitik**:

1. **State (Penyimpanan Fisik):** Tabel fakta, tabel dimensi, dan *snapshot* data di data warehouse (misal: Iceberg, Parquet, Snowflake). Model ini dioptimalkan untuk efisiensi *I/O*, partisi, dan kompresi, bukan kenyamanan formulasi metrik bisnis.
2. **Logic (Semantik & Standar Metrik):** Lapisan deklaratif yang memetakan relasi antar entitas, aturan agregasi (misal: `SUM`, `COUNT DISTINCT`, non-additivity), resolusi *grain*, perlakuan zona waktu, serta kontrol akses berbasis atribut (*Attribute-Based Access Control* / ABAC).
3. **Presentation (Konsumsi Data):** Dasbor visual, kueri ad-hoc analis, *reverse ETL*, atau *autonomous agent* yang meminta data dalam format: `"Berapa Net Revenue per Region untuk Q3 2024?"` tanpa perlu mengetahui relasi tabel fisik di baliknya.

Di era AI dan *Autonomous Agents*, ketiadaan semantic layer memaksa LLM mengasumsikan relasi SQL dan rumus bisnis secara probabilistik. Hal ini menjadi akar utama kegagalan otomatisasi analitik (halusinasi SQL, agregasi ganda, serta pelanggaran *join path*). *Enterprise Semantic Layer* mengubah interaksi data menjadi pendekatan deterministik: LLM hanya memilih metrik dan dimensi dari katalog semantik terverifikasi, sementara *engine* semantik menerjemahkannya ke SQL yang valid secara matematis.

---

### 3. Why It Matters

Di tingkat enterprise, ketiadaan *semantic layer* memicu kondisi **"Metric Divergence Hell"**:

* **Inkonsistensi Nilai Finansial:** Laporan *Executive Board* menampilkan angka *Monthly Recurring Revenue* (MRR) yang berbeda antara dasbor Finance ($1.2M) dan dasbor Sales ($1.4M). Perbedaan ini timbul karena Finance menghitung pengembalian dana (*refunds*) pada tanggal pemrosesan bank, sedangkan Sales menghitungnya pada tanggal permintaan tiket pelanggan.
* **Fan-Out & Chasm Traps:** Penggabungan tabel `fct_orders` dan `fct_order_refunds` melalui dimensi `dim_customer` tanpa penanganan *grain* yang benar menyebabkan nilai total transaksi terduplikasi (*fan-out*), melipatgandakan nilai pendapatan secara semu.
* **Kerapuhan Autonomous Data Agents:** *Autonomous Agent* berbasis LLM yang diberikan akses langsung ke skema database dengan ratusan tabel akan gagal menentukan tabel fakta mana yang valid untuk analisis retensi, serta sering salah memilih kolom tanggal (misal: `created_at` vs `settled_at`).
* **Technical Debt & High Maintenance:** Perubahan definisi metrik dasar (misal: pengecualian akun uji coba internal) menuntut modifikasi manual pada ratusan kueri SQL tersimpan di dasbor BI, skrip ETL hilir, dan *prompt template* LLM.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut menggambarkan siklus hidup dari metadata sumber data fisik hingga dikonsumsi oleh lapisan analitik dan agen cerdas:

```
+-----------------------------------------------------------------------------------+
|                            PHYSICAL STORAGE LAYER                                 |
|   +-----------------------+     +-----------------------+     +---------------+   |
|   |   orders (Fact)       |     | order_items (Fact)    |     | customers     |   |
|   |   grain: order_id     |     | grain: item_id        |     | (Dimension)   |   |
+---+-----------+-----------+-----+-----------+-----------+-----+-------+-------+---+
                |                             |                         |            
                |                             |                         |            
+---------------+-----------------------------+-------------------------+-----------+
|                          ENTERPRISE SEMANTIC LAYER ENGINE                         |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Semantic Manifest Repository (YAML Declarative Models / Git-versioned)       |  |
|  |  - Dimensions: [customer.id, customer.country, customer.tier]                |  |
|  |  - Metrics: [gross_revenue, net_revenue, active_customers]                 |  |
|  |  - Joins / Relations: Primary & Foreign Keys, Grain Definition, Join Type   |  |
|  +---------------------------------------+-------------------------------------+  |
|                                          |                                        |
|  +---------------------------------------v-------------------------------------+  |
|  | Core Compiler & Validation Engine                                           |  |
|  |   1. Semantic Type Checker (Validasi dependensi siklik & grain mismatch)    |  |
|  |   2. Topology Graph Builder (Resolusi DAG Join Path & Anti-Trap Algorithm)   |  |
|  |   3. Dynamic SQL Transpiler (Dialect Engine: DuckDB / Snowflake / BigQuery) |  |
|  |   4. Policy & Security Enforcer (Row-Level Security & Masking ABAC)         |  |
|  +---------------------------------------+-------------------------------------+  |
|                                          |                                        |
|  +---------------------------------------v-------------------------------------+  |
|  | Performance & Caching Fabric                                                |  |
|  |  - Pre-aggregation Router (Rollup Materialization)                          |  |
|  |  - In-Memory Semantic Cache (Redis / Query Result Cache)                    |  |
+--+---------------------------------------+-------------------------------------+--+
                                           |                                         
              +----------------------------+---------------------------+             
              |                                                        |             
+-------------v-------------------------------+  +---------------------v------------+
|        DOWNSTREAM CONSUMERS                 |  |      AGENTIC & API WORKFLOWS     |
|  - Modern BI (Tableau, Superset, Evidence)  |  |  - Autonomous Agents (ReAct)     |
|  - Reverse ETL Pipelines (Hightouch, Census)|  |  - MCP (Model Context Protocol)  |
|  - Notebooks (Python, DuckDB, R)            |  |  - Metric Catalog API (GraphQL)  |
+---------------------------------------------+  +----------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Formalisasi Definisi Metrik (The Anatomy of a Metric)

Metrik bukan sekadar kolom agregasi SQL (seperti `SUM(amount)`). Metrik formal merupakan tuple matematika:

$$\mathcal{M} = \langle \mathcal{E}, \mathcal{F}, \mathcal{A}, \mathcal{T}, \mathcal{G}, \mathcal{F}_{filter} \rangle$$

* $\mathcal{E}$ (Entity): Entitas bisnis yang dievaluasi (misal: `Customer`, `Order`, `Transaction`).
* $\mathcal{F}$ (Field): Kolom fisik target atau ekspresi komputasi dasar.
* $\mathcal{A}$ (Aggregation Function): Operator agregasi ($\sum, \text{count}, \text{count distinct}, \text{avg}, \text{percentile}$).
* $\mathcal{T}$ (Time Dimension Reference): Dimensi waktu referensi dasar (*spine dimension*) untuk analisis historis.
* $\mathcal{G}$ (Grain): Resolusi terendah dari metrik (misal: 1 baris per item pesanan).
* $\mathcal{F}_{filter}$ (Predicate Filters): Kondisi logika pembatas (misal: `status = 'COMPLETED' AND is_test = FALSE`).

#### B. Resolusi Masalah Relasional Data Warehouse

##### 1. Fan-Out Trap
Terjadi ketika tabel berelasi $1:N$ digabungkan dengan tabel lain yang juga memiliki relasi $1:N$, atau saat tabel dimensi digabungkan dengan tabel fakta yang memiliki granularitas lebih rendah tanpa pre-agregasi.

* **Kasus:** Menggabungkan tabel `orders` ($1$) ke `order_items` ($N$) lalu mengagregasikan metrik dari tabel `orders` (misal: biaya pengiriman/`shipping_fee`).
* **Akibat:** `shipping_fee` terakumulasi sebanyak $N$ kali (jumlah baris di `order_items`).
* **Solusi Semantic Engine:** *Subquery pre-aggregation* atau *Split-and-Join Strategy*. Nilai `shipping_fee` diagregasikan terlebih dahulu pada tingkat `order_id` sebelum digabungkan ke set dimensi lainnya.

##### 2. Chasm Trap
Terjadi ketika dua tabel fakta independen yang saling berhubungan melalui satu tabel dimensi bersama (*conformed dimension*) digabungkan dalam satu kueri *join* paralel.

* **Kasus:** Menghitung total `order_amount` dari `orders` dan `refund_amount` dari `refunds` berdasarkan `customer_id`.
* **Akibat:** Terjadi operasi *Cartesian product* antara `orders` dan `refunds` untuk setiap pelanggan, menghasilkan nilai agregasi yang jauh lebih tinggi dari data sebenarnya.
* **Solusi Semantic Engine:** *Multi-pass SQL Execution*. Engine menghasilkan kueri SQL terpisah untuk masing-masing tabel fakta, lalu menyatukan (*coalescing*) hasilnya menggunakan `FULL OUTER JOIN` pada level dimensi bersama.

#### C. Topological Sort pada Graph Semantik

Definisi metrik dapat bergantung pada metrik lain (*derived/composite metrics*, contoh: $\text{AOV} = \frac{\text{Gross Revenue}}{\text{Total Orders}}$). *Engine* semantik membangun graf berarah tanpa siklus (*Directed Acyclic Graph* / DAG) dari node metrik dan relasi tabel. Kompiler melakukan *topological sort* untuk memastikan setiap metrik dependensi telah dihitung sebelum metrik turunan dieksekusi.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi *Semantic Layer Engine* modular berbasis Python yang mendemonstrasikan parsing deklaratif, resolusi relasi graf semantik, pencegahan *Fan-Out Trap*, dan translasi ke SQL dinamis dialek DuckDB/ANSI SQL.

```python
"""
Enterprise Semantic Layer Compiler & Metric Resolver
Author: Principal Technical Curriculum Architect & Principal Data Platform Engineer
Description: Modular, declarative semantic engine resolving Fan-Out/Chasm traps
             via multi-pass SQL compilation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# 1. DOMAIN MODELS & DECLARATIVE SCHEMAS
# ============================================================================

class AggregationType(str, Enum):
    SUM = "SUM"
    COUNT = "COUNT"
    COUNT_DISTINCT = "COUNT_DISTINCT"
    AVG = "AVG"
    MIN = "MIN"
    MAX = "MAX"


class JoinType(str, Enum):
    INNER = "INNER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FULL = "FULL"


class SemanticDimension(BaseModel):
    name: str = Field(..., description="Nama eksposur dimensi (e.g., customer_country)")
    physical_column: str = Field(..., description="Kolom fisik di tabel (e.g., country)")
    table_name: str = Field(..., description="Tabel sumber dimensi")
    data_type: str = Field(default="VARCHAR")


class SemanticMetric(BaseModel):
    name: str = Field(..., description="Pengenal unik metrik (e.g., net_sales)")
    table_name: Optional[str] = Field(None, description="Tabel fakta acuan")
    expression: str = Field(..., description="Kolom target atau kalkulasi matematis")
    aggregation: Optional[AggregationType] = Field(
        None, description="Tipe fungsi agregasi dasar"
    )
    filter_predicate: Optional[str] = Field(
        None, description="Filter wajib (e.g., is_valid = true)"
    )
    depends_on: List[str] = Field(
        default_factory=list, description="Metrik lain yang menjadi prasyarat kalkulasi"
    )
    is_derived: bool = Field(
        default=False, description="Apakah metrik dihitung dari metrik lain"
    )

    @field_validator("depends_on")
    @classmethod
    def validate_derived_state(cls, v: List[str], info) -> List[str]:
        is_derived = info.data.get("is_derived", False)
        if is_derived and not v:
            raise ValueError("Derived metric wajib memiliki minimal satu metrik pada 'depends_on'")
        if not is_derived and v:
            raise ValueError("Non-derived metric tidak boleh memiliki 'depends_on'")
        return v


class SemanticJoin(BaseModel):
    left_table: str
    right_table: str
    left_on: str
    right_on: str
    join_type: JoinType = JoinType.LEFT


class SemanticManifest(BaseModel):
    name: str
    tables: Set[str]
    dimensions: Dict[str, SemanticDimension]
    metrics: Dict[str, SemanticMetric]
    joins: List[SemanticJoin]


# ============================================================================
# 2. SEMANTIC COMPILER ERRORS
# ============================================================================

class SemanticCompilerError(Exception):
    """Base exception class for semantic compilation errors."""
    pass


class CyclicDependencyError(SemanticCompilerError):
    """Raised when derived metrics contain circular references."""
    pass


class InvalidPathResolutionError(SemanticCompilerError):
    """Raised when there is no viable join path between tables."""
    pass


class MissingEntityError(SemanticCompilerError):
    """Raised when a requested metric or dimension is not found."""
    pass


# ============================================================================
# 3. SEMANTIC ENGINE & TOPOLOGY MANAGER
# ============================================================================

class SemanticEngine:
    def __init__(self, manifest: SemanticManifest):
        self.manifest = manifest
        self.topology_graph = nx.Graph()
        self.metric_dag = nx.DiGraph()
        self._build_graphs()

    def _build_graphs(self) -> None:
        """Membangun graph relasi tabel dan DAG dependensi metrik."""
        # 1. Build Physical Relational Graph
        for tbl in self.manifest.tables:
            self.topology_graph.add_node(tbl)

        for j in self.manifest.joins:
            self.topology_graph.add_edge(
                j.left_table,
                j.right_table,
                left_on=j.left_on,
                right_on=j.right_on,
                join_type=j.join_type,
            )

        # 2. Build Metric Dependency DAG
        for m_name, m_val in self.manifest.metrics.items():
            self.metric_dag.add_node(m_name)
            for dep in m_val.depends_on:
                self.metric_dag.add_edge(dep, m_name)

        if not nx.is_directed_acyclic_graph(self.metric_dag):
            cycle = nx.find_cycle(self.metric_dag, orientation="original")
            raise CyclicDependencyError(f"Terdeteksi siklus pada metrik: {cycle}")

    def resolve_join_path(self, source_table: str, target_table: str) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Mencari jalur join terpendek untuk mencegah multi-path fan-out tak terduga."""
        if source_table == target_table:
            return []
        try:
            nodes_path = nx.shortest_path(self.topology_graph, source=source_table, target=target_table)
        except nx.NetworkXNoPath:
            raise InvalidPathResolutionError(
                f"Tidak ditemukan jalur join yang valid antara '{source_table}' dan '{target_table}'"
            )

        path_edges = []
        for i in range(len(nodes_path) - 1):
            u = nodes_path[i]
            v = nodes_path[i + 1]
            edge_data = self.topology_graph.get_edge_data(u, v)
            path_edges.append((u, v, edge_data))
        return path_edges

    def resolve_metric_execution_order(self, metric_names: List[str]) -> List[str]:
        """Topological sort untuk mengevaluasi metrik dasar sebelum metrik turunan."""
        subgraph_nodes = set()
        for m in metric_names:
            if m not in self.manifest.metrics:
                raise MissingEntityError(f"Metrik '{m}' tidak terdefinisi dalam skema.")
            subgraph_nodes.update(nx.ancestors(self.metric_dag, m))
            subgraph_nodes.add(m)

        sub_dag = self.metric_dag.subgraph(subgraph_nodes)
        return list(nx.topological_sort(sub_dag))


# ============================================================================
# 4. QUERY COMPILER & TRANSPILER
# ============================================================================

class SemanticQueryCompiler:
    def __init__(self, engine: SemanticEngine):
        self.engine = engine

    def compile(self, requested_metrics: List[str], requested_dimensions: List[str]) -> str:
        """
        Mengompilasi permintaan metrik dan dimensi menjadi SQL aman (Anti-Trap Query).
        Menggunakan arsitektur Common Table Expressions (CTE) independen per tabel fakta.
        """
        # Validasi eksistensi dimensi
        dim_objects: List[SemanticDimension] = []
        for d in requested_dimensions:
            if d not in self.engine.manifest.dimensions:
                raise MissingEntityError(f"Dimensi '{d}' tidak terdaftar pada semantic manifest.")
            dim_objects.append(self.engine.manifest.dimensions[d])

        # Resolusi hierarki ketergantungan metrik
        execution_order = self.engine.resolve_metric_execution_order(requested_metrics)
        base_metrics = [
            self.engine.manifest.metrics[m]
            for m in execution_order
            if not self.engine.manifest.metrics[m].is_derived
        ]
        derived_metrics = [
            self.engine.manifest.metrics[m]
            for m in execution_order
            if self.engine.manifest.metrics[m].is_derived
        ]

        # Kelompokkan metrik dasar berdasarkan tabel fakta untuk isolasi agregasi (Solusi Fan-Out & Chasm Traps)
        metrics_by_table: Dict[str, List[SemanticMetric]] = {}
        for bm in base_metrics:
            assert bm.table_name is not None
            metrics_by_table.setdefault(bm.table_name, []).append(bm)

        ctes: List[str] = []
        cte_names: List[str] = []

        # Tentukan tabel dimensi primer (jika ada dimensi yang diminta)
        primary_dim_table = dim_objects[0].table_name if dim_objects else None

        # Bangun CTE per tabel fakta dengan agregasi terisolasi
        for fact_table, metrics_list in metrics_by_table.items():
            cte_name = f"agg_{fact_table}"
            cte_names.append(cte_name)

            select_elements: List[str] = []
            group_by_indices: List[str] = []
            joins_needed: List[str] = []
            current_dim_idx = 1

            # Hubungkan tabel fakta ke dimensi yang diminta dalam CTE yang terisolasi
            if primary_dim_table:
                path = self.engine.resolve_join_path(fact_table, primary_dim_table)
                for u, v, edge_data in path:
                    # Pastikan kita join ke arah yang benar
                    left_col = edge_data["left_on"] if u == fact_table else edge_data["right_on"]
                    right_col = edge_data["right_on"] if u == fact_table else edge_data["left_on"]
                    joins_needed.append(
                        f"{edge_data['join_type'].value} JOIN {v} ON {u}.{left_col} = {v}.{right_col}"
                    )

                for dim in dim_objects:
                    select_elements.append(f"{dim.table_name}.{dim.physical_column} AS {dim.name}")
                    group_by_indices.append(str(current_dim_idx))
                    current_dim_idx += 1

            # Kompilasi agregasi metrik
            for m in metrics_list:
                agg_fn = m.aggregation.value if m.aggregation else "SUM"
                pred = f" FILTER (WHERE {m.filter_predicate})" if m.filter_predicate else ""
                select_elements.append(f"{agg_fn}({m.expression}){pred} AS {m.name}")

            joins_clause = "\n        ".join(joins_needed) if joins_needed else ""
            group_by_clause = f"\n    GROUP BY {', '.join(group_by_indices)}" if group_by_indices else ""

            cte_sql = f"""{cte_name} AS (
    SELECT
        {', '.join(select_elements)}
    FROM {fact_table}
    {joins_clause}{group_by_clause}
)"""
            ctes.append(cte_sql)

        # Bangun CTE Final yang menggabungkan seluruh CTE terisolasi
        final_selects: List[str] = []
        if dim_objects:
            for dim in dim_objects:
                final_selects.append(f"COALESCE({', '.join([f'{c}.{dim.name}' for c in cte_names])}) AS {dim.name}")

        # Masukkan metrik dasar
        for bm in base_metrics:
            assert bm.table_name is not None
            final_selects.append(f"agg_{bm.table_name}.{bm.name}")

        # Masukkan kalkulasi metrik turunan
        for dm in derived_metrics:
            final_selects.append(f"({dm.expression}) AS {dm.name}")

        # Logika penggabungan CTE
        if len(cte_names) == 1:
            from_clause = f"FROM {cte_names[0]}"
        else:
            base_cte = cte_names[0]
            other_ctes = cte_names[1:]
            join_conditions = []
            for oc in other_ctes:
                conds = [f"{base_cte}.{dim.name} = {oc}.{dim.name}" for dim in dim_objects]
                cond_str = " AND ".join(conds) if conds else "1=1"
                join_conditions.append(f"FULL OUTER JOIN {oc} ON {cond_str}")
            from_clause = f"FROM {base_cte}\n" + "\n".join(join_conditions)

        # Filter output akhir hanya pada metrik & dimensi yang diminta
        requested_output = [d for d in requested_dimensions] + [m for m in requested_metrics]
        
        full_sql = f"""WITH
{',\\n'.join(ctes)},
consolidated_stage AS (
    SELECT
        {', '.join(final_selects)}
    {from_clause}
)
SELECT
    {', '.join(requested_output)}
FROM consolidated_stage;"""

        return full_sql


# ============================================================================
# 5. DEMONSTRATION & VERIFICATION PIPELINE
# ============================================================================

def initialize_sample_semantic_layer() -> SemanticEngine:
    """Menginisialisasi konfigurasi pengujian skema data warehouse e-commerce."""
    manifest = SemanticManifest(
        name="Enterprise E-Commerce Semantics",
        tables={"orders", "order_items", "refunds", "customers"},
        dimensions={
            "customer_id": SemanticDimension(
                name="customer_id", physical_column="id", table_name="customers"
            ),
            "country": SemanticDimension(
                name="country", physical_column="country_code", table_name="customers"
            ),
        },
        metrics={
            "gross_revenue": SemanticMetric(
                name="gross_revenue",
                table_name="order_items",
                expression="price * quantity",
                aggregation=AggregationType.SUM,
                filter_predicate="is_cancelled = FALSE",
            ),
            "total_orders": SemanticMetric(
                name="total_orders",
                table_name="orders",
                expression="order_id",
                aggregation=AggregationType.COUNT_DISTINCT,
            ),
            "total_refunded": SemanticMetric(
                name="total_refunded",
                table_name="refunds",
                expression="refund_amount",
                aggregation=AggregationType.SUM,
            ),
            # Derived Metrics:
            "net_revenue": SemanticMetric(
                name="net_revenue",
                expression="gross_revenue - COALESCE(total_refunded, 0.0)",
                is_derived=True,
                depends_on=["gross_revenue", "total_refunded"],
            ),
            "aov": SemanticMetric(
                name="aov",
                expression="gross_revenue / NULLIF(total_orders, 0)",
                is_derived=True,
                depends_on=["gross_revenue", "total_orders"],
            ),
        },
        joins=[
            SemanticJoin(
                left_table="orders",
                right_table="customers",
                left_on="customer_id",
                right_on="id",
                join_type=JoinType.INNER,
            ),
            SemanticJoin(
                left_table="order_items",
                right_table="orders",
                left_on="order_id",
                right_on="order_id",
                join_type=JoinType.INNER,
            ),
            SemanticJoin(
                left_table="refunds",
                right_table="orders",
                left_on="order_id",
                right_on="order_id",
                join_type=JoinType.INNER,
            ),
        ],
    )
    return SemanticEngine(manifest)


if __name__ == "__main__":
    import json

    engine = initialize_sample_semantic_layer()
    compiler = SemanticQueryCompiler(engine)

    print("--- 1. SEMANTIC DAG TOPOLOGY ---")
    print(f"Nodes: {list(engine.metric_dag.nodes)}")
    print(f"Execution sequence for 'aov': {engine.resolve_metric_execution_order(['aov'])}")

    print("\n--- 2. COMPILED ANTI-TRAP MULTI-PASS SQL QUERY ---")
    compiled_sql = compiler.compile(
        requested_metrics=["net_revenue", "aov"],
        requested_dimensions=["customer_id", "country"],
    )
    print(compiled_sql)
```

---

### 7. Edge Cases & Failure Modes

Pada penggelaran produksi, *semantic engine* harus mengantisipasi kegagalan sistemik dan data anomali:

| Kasus Ekstrem (*Edge Case*) | Dampak Kegagalan | Strategi Pencegahan (*Mitigation Strategy*) |
| :--- | :--- | :--- |
| **Non-Additive Metrics over Time Spine** | Metrik semi-aditif (seperti saldo kas harian `ending_balance` atau stok inventaris) dijumlahkan secara keliru jika pengguna meminta agregasi bulanan. | Definisikan atribut agregasi `SEMI_ADDITIVE` dengan parameter `default_time_spine_aggregation = LAST_VALUE` di dalam manifes semantik. |
| **Division-by-Zero pada Derived Metrics** | Eksekusi kueri gagal total (*fatal query exception*) pada *data warehouse* saat penyebut bernilai nol. | Translasi wajib menyuntikkan fungsi pelindung seperti `NULLIF(denominator, 0)` secara transparan saat mengompilasi metrik turunan bertipe rasio/pembagian. |
| **Dimension Incompatible Grain** | Pengguna meminta metrik `total_order_items` dikelompokkan berdasarkan dimensi tingkat item pengiriman (`tracking_number`), padahal tidak ada relasi langsung dari fakta ke dimensi tersebut. | Lakukan validasi derajat ketercapaian relasi (*reachability analysis*) pada graf topologi; tolak kompilasi kueri dan lempar status HTTP 422 (*Unprocessable Entity*) dengan rekomendasi dimensi yang valid. |
| **High Cardinality Dimension Explosion** | Dimensi dengan kardinalitas sangat tinggi (seperti `session_cookie_id`) diminta bersama 10 metrik terdistribusi, memicu *out-of-memory error* (OOM) pada mesin database. | Terapkan *hard guardrails* pada semantic compiler: tolak kueri tanpa batasan filter waktu (`WHERE date >= ...`) jika kardinalitas dimensi historis melampaui ambang batas aman (misal: $> 1.000.000$ entitas unik). |

---

### 8. Trade-offs & Alternatif Solusi

Setiap perancangan arsitektur analitik menuntut kompromi struktural:

```
[ Trade-off Landscape ]
Decoupled Semantic Layer (Cube, dbt-SL) <===========> In-BI Modeling (Tableau, Looker)
           |                                                      |
    (+) High Agnosticity                                   (+) Native Visual Speed
    (+) AI/Agent Grounding                                 (-) Vendor Lock-in
    (-) High Initial Complexity                            (-) Metric Divergence Sprawl
```

| Pendekatan | Keunggulan Utama | Kelemahan Utama | Kasus Penggunaan Ideal |
| :--- | :--- | :--- | :--- |
| **Decoupled Semantic Layer** (Cube, MetricFlow/dbt-SL) | Konsistensi absolut lintas visualisasi BI, API, aplikasi internal, dan LLM data agents. *Single point of definition*. | Menambah satu lapisan latensi jaringan (*network hop*) dan menuntut tata kelola metadata yang disiplin. | Organisasi enterprise multi-alat BI dengan integrasi *Autonomous Agent*. |
| **In-BI Semantic Models** (Looker LookML, PowerBI Dataset) | Terintegrasi sangat ketat dengan visualisasi bawaan, performa *caching* lokal sangat cepat, mudah diadopsi analis BI konvensional. | Terkunci (*vendor lock-in*). LLM dan sistem eksternal tidak dapat mengakses logika bisnis tanpa reverse-engineering atau lisensi pengguna mahal. | Organisasi yang 100% menggunakan ekosistem vendor tunggal tanpa integrasi *external agent*. |
| **Warehouse-Native Views / dbt Models (SQL Tables)** | Nol dependensi perangkat lunak tambahan, kueri dijalankan langsung pada mesin komputasi gudang data. | Rentan terhadap *fan-out trap* dinamis jika di-join di hilir. Perubahan dimensi memerlukan pembuatan model materialisasi baru secara berulang. | Tim data tahap awal (*early stage*) dengan kompleksitas metrik dan variasi dimensi rendah. |

---

### 9. Best Practices & Standar Industri

1. **Metrics-as-Code via GitOps:**
   * Seluruh manifes model metrik harus tersimpan dalam repositori Git dalam format deklaratif (YAML/Python).
   * Setiap penggabungan (*merge*) ke cabang utama wajib melewati *pipeline* CI/CD yang menguji:
     * Ketiadaan referensi sirkular (*cyclic dependencies*).
     * Kesesuaian tipe data dimensi fisik.
     * Pengujian regresi SQL otomatis: memverifikasi bahwa kueri hasil kompilasi menghasilkan nilai metrik yang identik dengan *baseline* historis.

2. **Standardisasi Tata Nama Metrik (Strict Taxonomy):**
   * Gunakan pola penamaan baku: `[entitas]_[sifat_kuantitatif]_[modifier]`
   * *Contoh yang benar:* `order_revenue_gross`, `customer_count_active_30d`.
   * *Hindari:* `rev2_final`, `clean_active_users`.

3. **Isolasi Logika Akses (Semantic ABAC):**
   Terapkan aturan tata kelola data langsung di *semantic layer*, bukan di level dasbor:
   ```yaml
   dimensions:
     - name: salary
       physical_column: salary_amount
       table_name: fct_payroll
       security_policy:
         masking: "REDACT"
         allow_roles: ["HR_ADMIN", "CFO"]
   ```

4. **Persiapan Grounding Data untuk Agen Otonom (MCP/LLM Ready):**
   Setiap entitas metrik dan dimensi wajib memiliki metadata deskriptif tekstual yang komprehensif. LLM tidak dapat memprediksi tujuan metrik tanpa konteks operasional bisnis:
   ```yaml
   metric:
     name: customer_churn_rate_monthly
     description: "Persentase pelanggan aktif pada awal bulan yang tidak memperbarui langganan hingga akhir bulan berjalan. Tidak memperhitungkan akun masa percobaan (trial)."
   ```

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah Senior BI Analyst di platform e-commerce regional. Manajemen mengeluhkan nilai pendapatan dan pengembalian dana (*refunds*) yang melonjak drastis saat dianalisis bersamaan per regional. Tugas Anda adalah mengimplementasikan Semantic Layer sederhana menggunakan Python dan DuckDB secara langsung, mendemonstrasikan bagaimana kueri SQL biasa memicu *Fan-Out Trap*, serta menyelesaikan masalah tersebut menggunakan *multi-pass isolation*.

#### Langkah 1: Persiapan Database dan Data Dummy
Buat skrip `setup_lab.py` untuk menyiapkan basis data DuckDB lokal dalam memori dengan data yang mereplikasi masalah *grain*:

```python
# setup_lab.py
import duckdb

def get_connection():
    con = duckdb.connect(database=":memory:")
    
    # 1. Tabel Dimensi: Customers (1 baris per customer)
    con.execute("""
    CREATE TABLE dim_customers AS SELECT * FROM (VALUES
        (1, 'ID', 'Indonesia'),
        (2, 'SG', 'Singapore')
    ) AS t(customer_id, country_code, country_name);
    """)

    # 2. Tabel Fakta: Orders (1 customer dapat memiliki banyak orders)
    con.execute("""
    CREATE TABLE fct_orders AS SELECT * FROM (VALUES
        (101, 1, 100.0),
        (102, 1, 150.0),
        (103, 2, 200.0)
    ) AS t(order_id, customer_id, total_amount);
    """)

    # 3. Tabel Fakta: Order Items (1 order memiliki banyak items -> Grain lebih dalam)
    con.execute("""
    CREATE TABLE fct_order_items AS SELECT * FROM (VALUES
        (1001, 101, 'SKU-A', 50.0, 1),
        (1002, 101, 'SKU-B', 50.0, 1),
        (1003, 102, 'SKU-C', 150.0, 1),
        (1004, 103, 'SKU-D', 200.0, 1)
    ) AS t(item_id, order_id, sku, price, qty);
    """)

    # 4. Tabel Fakta: Refunds (1 order dapat memiliki banyak refund event)
    con.execute("""
    CREATE TABLE fct_refunds AS SELECT * FROM (VALUES
        (501, 101, 20.0),
        (502, 101, 30.0)
    ) AS t(refund_id, order_id, refund_amount);
    """)
    
    return con

if __name__ == "__main__":
    con = get_connection()
    print("Schema initialized successfully.")
```

#### Langkah 2: Demonstrasi Kueri Analitik Cacat (The Trap)
Jalankan kueri SQL naif yang biasa dirancang oleh analis tanpa pemahaman semantik terisolasi:

```python
# run_naive_query.py
from setup_lab import get_connection

con = get_connection()

naive_sql = """
SELECT 
    c.country_name,
    SUM(o.total_amount) AS broken_total_orders,
    SUM(oi.price * oi.qty) AS broken_total_items,
    SUM(r.refund_amount) AS broken_total_refunds
FROM dim_customers c
LEFT JOIN fct_orders o ON c.customer_id = o.customer_id
LEFT JOIN fct_order_items oi ON o.order_id = oi.order_id
LEFT JOIN fct_refunds r ON o.order_id = r.order_id
GROUP BY c.country_name;
"""

print("--- HASIL KUERI NAIF (TERKENA FAN-OUT & CHASM TRAP) ---")
con.execute(naive_sql)
df_broken = con.fetchdf()
print(df_broken)
```

*Analisis Hasil Kueri Cacat:*
Untuk Indonesia (`country_name = 'Indonesia'`), transaksi `101` memiliki $2$ item dan $2$ refund. Penggabungan paralel tersebut menggandakan baris secara kartesian ($2 \text{ items} \times 2 \text{ refunds} = 4 \text{ baris}$), melipatgandakan metrik `broken_total_orders` menjadi tidak valid secara finansial.

#### Langkah 3: Implementasi Solusi Melalui Semantic Engine Resolver
Buat kueri yang dihasilkan oleh prinsip arsitektur *Semantic Layer* (Multi-Pass CTE dengan agregasi terisolasi sebelum *join*):

```python
# run_semantic_query.py
from setup_lab import get_connection

con = get_connection()

semantic_isolated_sql = """
WITH 
-- Tahap 1: Agregasi terisolasi untuk fct_orders
agg_orders AS (
    SELECT 
        c.country_name,
        SUM(o.total_amount) AS total_orders
    FROM fct_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.country_name
),
-- Tahap 2: Agregasi terisolasi untuk fct_order_items
agg_items AS (
    SELECT 
        c.country_name,
        SUM(oi.price * oi.qty) AS gross_items_revenue
    FROM fct_order_items oi
    JOIN fct_orders o ON oi.order_id = o.order_id
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.country_name
),
-- Tahap 3: Agregasi terisolasi untuk fct_refunds
agg_refunds AS (
    SELECT 
        c.country_name,
        SUM(r.refund_amount) AS total_refunded
    FROM fct_refunds r
    JOIN fct_orders o ON r.order_id = o.order_id
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.country_name
),
-- Tahap 4: Penyatuan seluruh fakta pada level Conformed Dimension (country_name)
dim_spine AS (
    SELECT DISTINCT country_name FROM dim_customers
)
SELECT 
    d.country_name,
    COALESCE(ao.total_orders, 0.0) AS safe_total_orders,
    COALESCE(ai.gross_items_revenue, 0.0) AS safe_gross_items_revenue,
    COALESCE(ar.total_refunded, 0.0) AS safe_total_refunded,
    (COALESCE(ai.gross_items_revenue, 0.0) - COALESCE(ar.total_refunded, 0.0)) AS net_merchandise_revenue
FROM dim_spine d
LEFT JOIN agg_orders ao ON d.country_name = ao.country_name
LEFT JOIN agg_items ai ON d.country_name = ai.country_name
LEFT JOIN agg_refunds ar ON d.country_name = ar.country_name;
"""

print("--- HASIL KUERI TERSTANDARISASI (SEMANTIC ENGINE COMPILATION) ---")
con.execute(semantic_isolated_sql)
df_corrected = con.fetchdf()
print(df_corrected)
```

#### Langkah 4: Tugas Mandiri (Self-Paced Challenge)
1. Modifikasi konfigurasi Pydantic *Semantic Layer* pada bagian 6 untuk menambahkan tabel dimensi baru: `dim_promotions` (dengan kolom `promo_id`, `promo_name`, `discount_rate`).
2. Tambahkan metrik baru: `total_discount_given` yang bersumber dari tabel fakta `fct_orders`.
3. Buat satu unit pengujian menggunakan `pytest` untuk memverifikasi bahwa kueri yang mengombinasikan `customer_country`, `net_revenue`, dan `aov` menghasilkan struktur CTE yang memisahkan penggabungan tabel fakta `refunds` dan `order_items`. Batalkan eksekusi jika terjadi referensi siklik antar metrik turunan.