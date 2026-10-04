# BAB 07: Enterprise Business Intelligence & Semantic Layer
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang Arsitektur Semantic Layer Terdistribusi:** Mengembangkan arsitektur *headless semantic layer* skala enterprise yang memisahkan definisi logika bisnis (metrik, dimensi) dari lapisan penyimpanan (data warehouse/lakehouse) dan lapisan konsumsi (BI tools, aplikasi internal, agen AI).
- **Mengimplementasikan Query Pushdown & Optimasi AST:** Memahami dan mengonfigurasi mekanisme translasi *Abstract Syntax Tree* (AST) dari kueri semantik menjadi SQL native dengan *pushdown predicates*, *partition pruning*, dan *projection optimization*.
- **Membangun Strategi Pre-aggregation & Caching Bertingkat:** Merancang skema agregasi bertingkat (*multi-level pre-aggregations*) menggunakan teknologi OLAP terdistribusi guna mencapai latensi kueri sub-detik untuk miliaran baris data.
- **Menerapkan Enterprise Security Matrix (RLS & CLS):** Mengonfigurasi *Row-Level Security* (RLS) dinamis dan *Column-Level Security* (CLS) berbasis identitas JWT/OAuth pada level semantik secara tersentralisasi.
- **Mengintegrasikan Semantic Layer dengan LLM & Autonomous Agents:** Membangun *schema context engine* yang mengekspos metadata semantik terstandardisasi untuk mencegah halusinasi metrik pada eksekusi Text-to-SQL dan AI-driven data agents.

---

### 2. Prerequisites
Sebelum memulai modul ini, Anda wajib menguasai:
- **Pemodelan Data Dimensional Lanjutan:** Memahami skema Kimball (*Conformed Dimensions*, *Accumulating Snapshot Fact Tables*, *Degenerate Dimensions*).
- **SQL Engineering Lanjutan:** Menguasai *Window Functions*, CTE, manipulasi partisi tabel, dan analisis rencana eksekusi (`EXPLAIN ANALYZE`).
- **Data Warehousing Modern:** Pengetahuan operasional mengenai mesin analitik kolumnar (Snowflake, BigQuery, ClickHouse, atau Trino).
- **Dasar Software Engineering:** Pemahaman deklaratif YAML/JSON, arsitektur microservices, dasar API (REST/GraphQL), dan protokol autentikasi (JWT/OIDC).

---

### 3. Concept & Internal Architecture (Mendalam)

Modern Enterprise Semantic Layer bukan sekadar abstraksi view SQL konvensional; ini adalah sistem terdistribusi yang bertindak sebagai *universal query router*, *compiler*, dan *cache coordinator*.

```
+-------------------------------------------------------------------------------+
|                       CONSUMPTION INTERFACES (APIs)                          |
|    +-------------+      +---------------+      +-------------------------+    |
|    | BI Tooling  |      | Custom WebApp |      |  AI / Autonomous Agent  |    |
|    | (REST/JDBC) |      | (GraphQL/SQL) |      |  (Text-to-SQL Context)  |    |
+----+------+------+------+-------+-------+------+------------+------------+----+
            |                     |                           |
            +---------------------+---------------------------+
                                  |
                                  v
+-------------------------------------------------------------------------------+
|                        ENTERPRISE SEMANTIC ENGINE                             |
|                                                                               |
|  1. Semantic Parser & Validator                                               |
|     - Menerima Query Semantik: Metric: `mrr`, GroupBy: `region`               |
|     - Validasi DAG, Tipe Relasi (1:N, N:M), & Atribut Dimensi                 |
|                                                                               |
|  2. Security & Policy Enforcement Engine                                      |
|     - Injeksi RLS (Tenant/Role filtering)                                     |
|     - Penegakan CLS (Masking kolom sensitif via PII policy)                   |
|                                                                               |
|  3. Query Planner & AST Generator                                             |
|     - Resolusi Chasm Traps & Fan Traps via Multi-pass SQL Generation          |
|     - Predicate Pushdown & Join Path Optimization                             |
|                                                                               |
|  4. Caching & Pre-Aggregation Optimizer                                       |
|     - Check In-Memory Cache (Redis) -> Hit? Return data                      |
|     - Check Pre-Aggregation Table (OLAP / ClickHouse) -> Hit? Return data     |
|     - Miss? Delegasikan ke Source Engine                                     |
+---------------------------------+---------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------------------+
|                        STORAGE & EXECUTION PLATFORM                           |
|       +-------------------+                   +------------------------+      |
|       | Source Lakehouse  |                   | External Pre-Agg OLAP  |      |
|       | (Snowflake/Trino) |                   | (ClickHouse/DuckDB)    |      |
+-------+-------------------+-------------------+------------------------+------+
```

#### Alur Kerja Internal Kompilasi Kueri:
1. **Penerimaan Query & Dekonstruksi Permintaan:** Query semantik diterima melalui interface deklaratif. Contoh:
   $$\text{Query} = \{ \text{Metrics: } [TotalRevenue], \text{ Dimensions: } [CustomerRegion], \text{ Filters: } [Date > '2024-01-01'] \}$$
2. **Graph Traversal & Join Path Determination:** Engine menganalisis Directed Acyclic Graph (DAG) model semantik untuk menemukan jalur *join* optimal antar entitas. Jika query melintasi dua tabel fakta berbeda melalui dimensi bersama (*chasm trap*), engine memecahnya menjadi kueri terpisah dengan agregasi lokal sebelum melakukan *full outer join* pada level akhir.
3. **Injeksi Kebijakan Keamanan (Security Policy Injection):** Engine membaca konteks sesi pengguna (Role, Tenant ID, Department) dari token JWT, lalu menyematkan predikat *WHERE* tersembunyi secara matematis ke dalam query AST sebelum serialisasi SQL.
4. **Pre-aggregation Routing:** Query Planner memeriksa ketersediaan tabel agregasi yang telah di-materialisasi. Jika granularitas waktu dan dimensi yang diminta tercakup dalam rollup agregat, AST diarahkan ulang ke tabel pre-agregasi untuk memangkas jutaan partisi mentah.
5. **SQL Transpilation & Pushdown:** AST diubah menjadi SQL dialek native sesuai target warehouse (Snowflake, BigQuery, ClickHouse) untuk memastikan komputasi dilakukan secara terdistribusi pada penyimpanan data.

---

### 4. Why & What

| Dimensi | Pendekatan Tradisional (BI-Centric / Spaghetti Views) | Enterprise Semantic Layer (Headless Semantic Engine) |
| :--- | :--- | :--- |
| **Pusat Definisi Metrik** | Tersebar di PowerBI DAX, Tableau Calculated Fields, dan script SQL ad-hoc. | **Tersentralisasi** dalam format *code-as-configuration* (Git-controlled YAML/JSON). |
| **Konsistensi Metrik** | Rendah; Metrik "Active User" memiliki definisi berbeda antar departemen. | **Mutlak**; Satu definisi kanonikal dikonsumsi oleh seluruh sistem secara serentak. |
| **Kinerja & Skalabilitas** | Menghantam database mentah; lonjakan latensi saat BI dashboard diakses banyak pengguna. | **Sub-detik** berkat *two-tier caching* dan pre-agregasi cerdas. |
| **Tata Kelola Keamanan** | Aturan RLS/CLS harus direplikasi di setiap dashboard dan aplikasi web. | **Zero-Trust Centralized**; Aturan RLS/CLS diterapkan otomatis pada level abstraksi data. |
| **Kesiapan AI / LLM** | LLM sering halusinasi SQL karena kompleksitas join fisik dan inkonsistensi penamaan kolom. | **Tinggi**; LLM berinteraksi dengan kontrak semantik yang telah divalidasi, bukan schema mentah. |

---

### 5. How (Workflow Detail)

Arsitektur produksi menerapkan alur siklus hidup metrik berikut:

```
[Developer/Analyst] 
        |
        | Git Commit (Metric/Model Defs)
        v
[CI/CD Engine] 
        |-- Syntax & Graph Integrity Validation
        |-- Schema Change Impact Analysis
        |-- Deployment to Semantic Engine
        v
[Semantic Engine Runtime]
        ^
        |--- 1. Client Request (JWT + Metric API)
        |--- 2. Auth Context Validation (Decode Tenant/Role)
        |--- 3. Query Compilation (AST -> SQL)
        |--- 4. Cache Evaluation (L1 Redis -> L2 Pre-agg)
        |--- 5. Target Execution (Pushdown ke Lakehouse)
        v
[Response Output JSON/Arrow]
```

1. **Pemodelan Deklaratif:** Data Analyst mendefinisikan entitas fisik (*source tables*), dimensi, ukuran (*measures*), dan relasi dalam format deklaratif.
2. **Validasi CI/CD:** Pipeline otomatis menguji integritas siklus referensi, mendeteksi *fan-traps*, dan memverifikasi kesesuaian tipe data pada database target.
3. **Penyebaran Model:** Engine semantik membaca konfigurasi baru tanpa *downtime* (*hot-reloading* via API atau reload kontainer).
4. **Resolusi Kueri Waktu-Nyata:** API klien meminta metrik dengan menyertakan token otentikasi; engine mengevaluasi hak akses, menyusun kueri SQL, memeriksa cache, menjalankan eksekusi pushdown, dan mengembalikan payload serialisasi Apache Arrow atau JSON.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Restoran Skala Dunia (Semantic Layer vs Direct Access)

- **Akses Langsung ke Database (Tanpa Semantic Layer):** Pelanggan (Pengguna BI, Aplikasi, AI) masuk langsung ke dapur gudang bahan baku (Data Warehouse mentah). Setiap pelanggan memotong sayur, merebus daging, dan menentukan sendiri resep rendang. Hasilnya: Dapur berantakan, risiko kebakaran tinggi (beban kueri berlebih), dan rasa masakan berbeda-beda di setiap meja.
- **Dengan Semantic Layer:** Terdapat **Kepala Koki dan Buku Menu Standar (Semantic Engine & Catalog)**. Pelanggan hanya memesan: *"Satu porsi Nasi Rendang"* (Metrik: `mrr`, Dimensi: `region`). Kepala koki memeriksa apakah rendang sudah matang di etalase penghangat (**Pre-aggregation Cache**). Jika ada, makanan disajikan dalam 2 detik. Jika tidak ada, staf dapur membuatkannya dengan prosedur resmi (**Pushdown SQL Compilation**) dengan bumbu yang terukur dan steril (**Security & Governance RLS**).

#### Diagram Transpilation AST

```
Input Request:
Metric: "arr"
Dimension: "customer_tier"
Context: { "org_id": "org_enterprise_42" }

       Query Request
             |
             v
   [ Abstract Syntax Tree ]
             |
      +------+------+
      |             |
   Dimension     Measure
  (customer_     (SUM(subscription_value) * 12)
    tier)           |
      |             +---- Filter Injection:
      |                   [org_id = 'org_enterprise_42']
      v
   Optimized Relational Algebra
             |
             v
  Generated SQL Execution Engine (Snowflake Dialect):
  -------------------------------------------------------------
  SELECT 
      c.customer_tier AS customer_tier,
      SUM(s.subscription_value * 12) AS arr
  FROM analytics_prod.subscriptions s
  INNER JOIN analytics_prod.customers c ON s.customer_id = c.id
  WHERE s.tenant_id = 'org_enterprise_42'
    AND s.status = 'ACTIVE'
  GROUP BY 1;
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Definisi Metrik Semantik Deklaratif (YAML)
Struktur konfigurasi metrik kanonikal bergaya dbt Semantic Layer / Cube:

```yaml
version: 2
semantic_models:
  - name: order_items
    model: ref('fct_order_items')
    entities:
      - name: order_item_id
        type: primary
      - name: order_id
        type: foreign
      - name: product_id
        type: foreign
      - name: customer_id
        type: foreign

    dimensions:
      - name: order_date
        type: time
        type_params:
          time_granularity: day
      - name: status
        type: categorical

    measures:
      - name: order_revenue
        agg: sum
        expr: item_amount_usd
      - name: total_distinct_orders
        agg: count_distinct
        expr: order_id

metrics:
  - name: net_order_revenue
    description: "Pendapatan kotor dikurangi diskon untuk pesanan selesai"
    type: simple
    type_params:
      measure: order_revenue
    filter: |
      status = 'COMPLETED'
```

#### Practical Example: Production Cube.js Schema dengan Multi-Tenant RLS & Pre-Aggregations
Implementasi arsitektur produksi menggunakan Cube.js Data Modeling Language (JavaScript/TypeScript interface) yang menangani keamanan multi-tenant dan pre-agregasi dinamis:

```javascript
cube(`EnterpriseSubscriptions`, {
  sql: `
    SELECT 
      s.subscription_id,
      s.tenant_id,
      s.customer_id,
      s.plan_type,
      s.monthly_recurring_revenue,
      s.created_at,
      s.is_active
    FROM analytics_dw.fct_subscriptions s
    WHERE {SECURITY_FILTER}
  `,

  // Row-Level Security dinamis diinjeksikan saat runtime berdasarkan JWT
  sql_table_filters: {
    SECURITY_FILTER: (ctx) => {
      if (!ctx.securityContext || !ctx.securityContext.tenantId) {
        throw new Error("Akses Ditolak: Konteks Keamanan Tenant Tidak Ada");
      }
      // System Admin dapat melihat seluruh data
      if (ctx.securityContext.role === 'SUPER_ADMIN') {
        return `1 = 1`;
      }
      return `s.tenant_id = ${cube.escape(ctx.securityContext.tenantId)}`;
    }
  },

  pre_aggregations: {
    // L2 Cache: Mempercepat komputasi MRR per Bulan per Plan Type
    mrrRollupByMonth: {
      measures: [EnterpriseSubscriptions.totalMrr, EnterpriseSubscriptions.subscriptionCount],
      dimensions: [EnterpriseSubscriptions.planType],
      time_dimension: EnterpriseSubscriptions.createdAt,
      granularity: `month`,
      partition_granularity: `month`,
      refresh_key: {
        every: `1 hour`,
        incremental: true,
        update_window: `7 day` // Memperbarui data mutasi 7 hari ke belakang
      },
      indexes: {
        categoryIndex: {
          columns: [EnterpriseSubscriptions.planType]
        }
      }
    }
  },

  joins: {
    EnterpriseCustomers: {
      relationship: `belongsTo`,
      sql: `${EnterpriseSubscriptions}.customer_id = ${EnterpriseCustomers}.customer_id`
    }
  },

  measures: {
    subscriptionCount: {
      type: `count`,
      title: `Jumlah Langganan Aktif`,
      filters: [{ sql: `${CUBE}.is_active = TRUE` }]
    },

    totalMrr: {
      type: `sum`,
      sql: `${CUBE}.monthly_recurring_revenue`,
      title: `Total Monthly Recurring Revenue`,
      format: `currency`
    },

    averageMrrPerTenant: {
      type: `number`,
      sql: `${totalMrr} / NULLIF(${subscriptionCount}, 0)`,
      title: `Rata-rata MRR per Langganan`,
      format: `currency`
    }
  },

  dimensions: {
    subscriptionId: {
      sql: `${CUBE}.subscription_id`,
      type: `string`,
      primary_key: true
    },

    planType: {
      sql: `${CUBE}.plan_type`,
      type: `string`
    },

    createdAt: {
      sql: `${CUBE}.created_at`,
      type: `time`
    }
  }
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
**Perusahaan:** Fintech Global Neobank (Melayani 12 juta pengguna, 400.000 entitas merchant, beroperasi di 4 yurisdiksi: SG, ID, VN, PH).
**Tantangan Arsitektur:**
1. **Metric Discrepancy:** Tim Finance menghitung "Gross Transaction Volume" (GTV) mengecualikan transaksi gagal dan refund, sementara Tim Growth menghitung GTV dari seluruh *attempted transactions*. Hal ini memicu disinformasi saat laporan ke dewan direksi.
2. **Kinerja Buruk:** Dashboard analitik merchant yang dibangun di atas Tableau dan microservices internal menghantam kluster Snowflake secara bersamaan, memicu *compute cost* sebesar \$80,000/bulan dengan p95 latency mencapai 18 detik.
3. **Isolasi Data Perbankan Ketat:** Regulasi data residency mewajibkan setiap merchant hanya boleh mengakses datanya sendiri tanpa celah kebocoran sedikit pun.

#### Desain Solusi
Sistem menerapkan **Headless Semantic Layer terdistribusi** menggunakan kluster kueri Cube.js yang terintegrasi dengan Snowflake (penyimpanan analitik primer) dan ClickHouse (mesin pre-agregasi terdistribusi).

```
[Merchant Portal / Internal Apps / BI Tools]
                    |
           HTTPS (Bearer JWT)
                    v
    [Load Balancer / Ingress Envoy]
                    |
  [Semantic Layer Service Cluster (Node.js/Rust)]
   - Token Decryption -> MerchantID: M_8819, Country: ID
   - Context Validation & Dynamic SQL Rewriting
                    |
       +------------+------------+
       | Cache Hit               | Cache Miss
       v                         v
[ClickHouse Pre-Agg Storage]  [Snowflake Enterprise Warehouse]
- Granularity: Day, Merchant  - Pushdown Scan with Partition Filter
- Latency: ~85ms             - Compute: Auto-suspend
- Latency: ~1.8s
```

#### Hasil Pengukuran Produksi
- **Penurunan Latensi:** p95 latency kueri dashboard turun dari **18.2 detik** menjadi **110 milidetik** berkat pre-agregasi partisi ClickHouse.
- **Efisiensi Biaya:** Biaya komputasi Snowflake turun **68%** (penghematan ~$54,000/bulan) karena 91% kueri berulang diselesaikan oleh L2 Pre-aggregations.
- **Audit Kepatuhan Keamanan:** 100% kueri yang dieksekusi memiliki parameter keamanan RLS statis yang diinjeksi via kode; nol insiden *cross-tenant data leakage* saat audit PCI-DSS.

---

### 9. Trade-offs

```
                      Query Speed / Latency
                              /\
                             /  \
                            /    \
                           /      \
                          /   *    \
                         / Pre-Agg  \
                        /  Optimized \
                       /              \
  Cost Efficiency ----+----------------+---- Data Freshness (Real-Time)
```

1. **Pre-aggregation Storage vs. Freshness Latency:**
   - *High Freshness:* Menghindari pre-agregasi dan menjalankan kueri langsung (*pure pushdown*) menjamin data real-time, tetapi membebani warehouse dan memicu biaya tinggi dengan latensi respons lambat (detik ke menit).
   - *Low Latency (Pre-aggregations):* Menghasilkan performa sub-detik melalui pembuatan tabel rollup otomatis, tetapi menimbulkan keterlambatan data (*sync interval* 15-60 menit) dan memerlukan storage tambahan di layer pre-agregasi.
2. **Normalized Semantic DAG vs. Compiled Flat Views:**
   - *Normalized Dynamic Graph:* Model data tetap berada dalam struktur normal (3NF/Kimball), dan engine menyusun *join* secara dinamis. Keunggulannya adalah fleksibilitas tinggi dan ukuran model ringkas, namun berisiko memicu *fan-out trap* jika relasi tidak dikalibrasi dengan presisi.
   - *Single Flat Table (One Big Table/OBT):* Menggabungkan seluruh data ke dalam satu tabel fisik raksasa. Menghilangkan kebutuhan relasi join saat runtime, tetapi meningkatkan redundansi data, komputasi ETL yang mahal, serta hilangnya granularitas data detail.
3. **Centralized Engine vs. Native Warehouse Semantics:**
   - Menggunakan platform semantic eksternal (Cube, MetricFlow) memungkinkan fleksibilitas multi-platform (bisa mengarahkan kueri ke Trino, Postgres, ClickHouse sekaligus). Namun, Anda harus mengelola infrastruktur independen (*extra maintenance cost*) dibandingkan menggunakan semantic built-in warehouse (misal: Snowflake Semantic Layer).

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Fan-Trap & Chasm-Trap pada Multiple One-to-Many Joins
*Gejala:* Nilai metrik `SUM(revenue)` berlipat ganda secara anomali saat digabungkan dengan dimensi pelanggan yang memiliki banyak baris interaksi (*tags*, *support tickets*).
*Akar Masalah:* Engine semantic mengeksekusi satu query SQL yang menggabungkan dua tabel fakta berbeda atau tabel dimensi dengan kardinalitas multi-arah:
```sql
-- SALAH: Menghasilkan duplikasi baris faktur karena join dengan support_tickets
SELECT 
    c.id,
    SUM(i.invoice_amount) AS total_invoiced,
    COUNT(t.id) AS total_tickets
FROM customers c
LEFT JOIN invoices i ON c.id = i.customer_id
LEFT JOIN support_tickets t ON c.id = t.customer_id
GROUP BY 1;
```
*Solusi Arsitektural:* Pisahkan menjadi CTE independen (*multi-pass query generation*) yang diagregasikan terlebih dahulu sebelum digabungkan:
```sql
-- BENAR: Mengisolasi agregasi sebelum final outer join
WITH inv AS (
    SELECT customer_id, SUM(invoice_amount) AS total_invoiced
    FROM invoices
    GROUP BY customer_id
),
tkt AS (
    SELECT customer_id, COUNT(id) AS total_tickets
    FROM support_tickets
    GROUP BY customer_id
)
SELECT 
    c.id,
    COALESCE(inv.total_invoiced, 0) AS total_invoiced,
    COALESCE(tkt.total_tickets, 0) AS total_tickets
FROM customers c
LEFT JOIN inv ON c.id = inv.customer_id
LEFT JOIN tkt ON c.id = tkt.customer_id;
```

#### Kesalahan 2: Pre-aggregation Partition Explosion
*Gejala:* Proses *build pre-aggregation* kehabisan disk space atau memori (*Out Of Memory* / OOM), dan durasi refresh cache berlangsung berjam-jam.
*Akar Masalah:* Mendefinisikan pre-agregasi dengan tingkat kardinalitas dimensi yang terlalu tinggi (contoh: menyertakan `user_id` atau `transaction_hash` ke dalam pre-agregasi bulanan).
*Troubleshooting:*
1. Pastikan dimensi pre-agregasi hanya berisi atribut bertipe *low-to-medium cardinality* (kategori, status, rentang negara, tanggal).
2. Lakukan partisi bertingkat (*monthly/daily partitioning*) sehingga proses *refresh* hanya menyentuh partisi aktif (data berjalan), bukan seluruh rentang historis.

#### Kesalahan 3: Missing Context Token pada Text-to-SQL AI Agents
*Gejala:* AI Data Agent mengeksekusi kueri agregasi global yang membocorkan data antar tenant saat merespons prompt pengguna.
*Solusi:* Wajibkan *runtime security wrapping*. AI Agent dilarang mengeksekusi SQL mentah langsung ke database; Agent hanya diizinkan memanggil API Semantic Layer dengan mempassing session token pengguna (`authorization: Bearer <jwt>`). Engine semantik yang bertanggung jawab menyuntikkan klausa RLS.

---

### 11. Best Practices (Production Checklist)

#### Desain Model Semantik
- [ ] Primary key dan Foreign key didefinisikan secara eksplisit di seluruh entitas semantik untuk mencegah ambiguasi relasi join.
- [ ] Format penamaan metrik menggunakan konvensi baku: `[verb/aggregation]_[entity]_[timeframe]` (contoh: `cum_revenue_30d`, `count_active_users_monthly`).
- [ ] Hindari penulisan logika transformasi rumit di dalam *measure*; letakkan logika parsing string dan data cleaning berat pada layer dbt model sebelumnya.

#### Kinerja & Caching
- [ ] Implementasikan strategi *Two-Tier Caching*: In-Memory L1 Cache (Redis) untuk query metadata dengan TTL pendek (10-30 detik), L2 Cache (Pre-aggregations) untuk analitik time-series besar.
- [ ] Terapkan konfigurasi *Rolling Window Refresh* pada tabel pre-agregasi (misal: refresh penuh untuk 7 hari terakhir; data historis yang sudah *immutable* diabaikan).
- [ ] Pastikan seluruh query pushdown ke target warehouse menggunakan klausa *partition pruning* (selalu menyaring berdasarkan rentang tanggal terindeks).

#### Tata Kelola & Keamanan
- [ ] Terapkan integrasi CI/CD untuk model semantik dengan validasi skema otomatis sebelum digabungkan (*merge*) ke branch utama.
- [ ] Konfigurasikan enkripsi transit (TLS 1.3) dan rest pada seluruh komunikasi antara Semantic Engine dan Lakehouse.
- [ ] Lakukan audit RLS berkala dengan membuat pengujian integrasi otomatis (*automated regression test*) menggunakan konteks pengguna dengan role berbeda.

---

### 12. Hands-on Practice

Buat struktur folder berikut di lingkungan kerja Anda:
```bash
mkdir -p hands-on/m02/semantic_engine
cd hands-on/m02/semantic_engine
```

#### Langkah 1: Siapkan Konfigurasi Lingkungan Lokal (Docker Compose)
Simpan file `docker-compose.yml` untuk menjalankan mock data warehouse (PostgreSQL) dan semantic layer runtime (Cube.js):

```yaml
version: '3.8'

services:
  postgres-dw:
    image: postgres:15-alpine
    container_name: m02_postgres_dw
    environment:
      POSTGRES_USER: dw_admin
      POSTGRES_PASSWORD: dw_password
      POSTGRES_DB: analytics_prod
    ports:
      - "5432:5432"
    volumes:
      - ./init-scripts:/docker-entrypoint-initdb.d

  cube-semantic-engine:
    image: cubejs/cube:latest
    container_name: m02_cube_engine
    environment:
      CUBEJS_DB_TYPE: postgres
      CUBEJS_DB_HOST: postgres-dw
      CUBEJS_DB_NAME: analytics_prod
      CUBEJS_DB_USER: dw_admin
      CUBEJS_DB_PASS: dw_password
      CUBEJS_API_SECRET: secret_jwt_token_must_be_long_and_secure_12345
      CUBEJS_DEV_MODE: "true"
    ports:
      - "4000:4000"
    volumes:
      - ./schema:/cube/conf/schema
    depends_on:
      - postgres-dw
```

#### Langkah 2: Inisialisasi Database Mock
Buat file `init-scripts/01_init.sql`:

```sql
CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE core.tenants (
    tenant_id VARCHAR(32) PRIMARY KEY,
    tenant_name VARCHAR(100) NOT NULL
);

CREATE TABLE core.dim_customers (
    customer_id VARCHAR(32) PRIMARY KEY,
    tenant_id VARCHAR(32) REFERENCES core.tenants(tenant_id),
    customer_name VARCHAR(100) NOT NULL,
    segment VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE core.fct_orders (
    order_id VARCHAR(32) PRIMARY KEY,
    tenant_id VARCHAR(32) REFERENCES core.tenants(tenant_id),
    customer_id VARCHAR(32) REFERENCES core.dim_customers(customer_id),
    order_date DATE NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(30) NOT NULL
);

-- Seed Data
INSERT INTO core.tenants VALUES 
('T_ALPHA', 'Tenant Alpha'),
('T_BETA', 'Tenant Beta');

INSERT INTO core.dim_customers VALUES 
('C1', 'T_ALPHA', 'Acme Corp', 'ENTERPRISE', '2023-01-10 10:00:00'),
('C2', 'T_ALPHA', 'Starlight LLC', 'SMB', '2023-03-15 11:30:00'),
('C3', 'T_BETA', 'Global Tech', 'ENTERPRISE', '2023-05-20 14:00:00');

INSERT INTO core.fct_orders VALUES 
('O101', 'T_ALPHA', 'C1', '2024-01-15', 5000.00, 'PAID'),
('O102', 'T_ALPHA', 'C1', '2024-01-20', 2500.00, 'PAID'),
('O103', 'T_ALPHA', 'C2', '2024-02-10', 1200.00, 'PAID'),
('O104', 'T_ALPHA', 'C2', '2024-02-12', 450.00, 'CANCELLED'),
('O105', 'T_BETA', 'C3', '2024-01-25', 18000.00, 'PAID'),
('O106', 'T_BETA', 'C3', '2024-02-05', 22000.00, 'PAID');
```

#### Langkah 3: Definisikan Semantic Model dengan Runtime RLS
Buat file `schema/Orders.js`:

```javascript
cube(`Orders`, {
  sql: `
    SELECT * FROM core.fct_orders
    WHERE 
      tenant_id = CASE 
        WHEN ${SECURITY_CONTEXT.role.unsafeSql()} = 'ADMIN' THEN tenant_id
        ELSE ${SECURITY_CONTEXT.tenantId.filter('tenant_id')}
      END
  `,

  joins: {
    Customers: {
      relationship: `belongsTo`,
      sql: `${CUBE}.customer_id = ${Customers}.customer_id`
    }
  },

  measures: {
    totalRevenue: {
      type: `sum`,
      sql: `amount`,
      filters: [{ sql: `${CUBE}.status = 'PAID'` }]
    },

    orderCount: {
      type: `count`
    },

    averageTicketSize: {
      type: `number`,
      sql: `${totalRevenue} / NULLIF(${orderCount}, 0)`
    }
  },

  dimensions: {
    orderId: {
      sql: `order_id`,
      type: `string`,
      primary_key: true
    },

    orderDate: {
      sql: `order_date`,
      type: `time`
    },

    status: {
      sql: `status`,
      type: `string`
    }
  }
});

cube(`Customers`, {
  sql: `SELECT * FROM core.dim_customers`,

  dimensions: {
    customerId: {
      sql: `customer_id`,
      type: `string`,
      primary_key: true
    },

    customerName: {
      sql: `customer_name`,
      type: `string`
    },

    segment: {
      sql: `segment`,
      type: `string`
    }
  }
});
```

#### Langkah 4: Eksekusi dan Validasi Lingkungan
Jalankan container:
```bash
docker compose up -d
```

Validasi API semantik menggunakan curl dengan mengirimkan payload terisolasi RLS:

```bash
# Generate Base64 Security Context Mock (Tenant Alpha)
# Context: {"tenantId": "T_ALPHA", "role": "USER"}
MOCK_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRJZCI6IlRfQUxQSEEiLCJyb2xlIjoiVVNFUiJ9.signature_placeholder"

curl -X POST http://localhost:4000/cubejs-api/v1/load \
  -H "Authorization: $MOCK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "measures": ["Orders.totalRevenue", "Orders.orderCount"],
      "dimensions": ["Customers.segment"]
    }
  }'
```

*Verifikasi Hasil:* Data yang kembali hanya berisi pesanan milik `T_ALPHA` (Acme Corp & Starlight LLC). Data transaksi \$40,000 milik `T_BETA` (Global Tech) secara otomatis diisolasi tanpa perlu menulis klausa `WHERE tenant_id = 'T_ALPHA'` pada payload kueri klien.

---

### 13. Exercise

#### Level Easy
Definisikan metrik semantik turunan baru bernama `Orders.cancellationRate` yang membagi jumlah pesanan dengan status `'CANCELLED'` terhadap total `Orders.orderCount`. Pastikan penanganan pembagian dengan angka nol (*zero division safety*) tercakup dalam formula.

#### Level Medium
Tambahkan pre-agregasi bernama `Orders.revenueByCustomerSegment` yang merangkum `totalRevenue` dan `orderCount` berdasarkan `Customers.segment` dan waktu `Orders.orderDate` dalam interval bulanan (`granularity: 'month'`). Konfigurasikan refresh rule yang memperbarui data setiap 2 jam.

#### Level Hard
Konfigurasikan Column-Level Security (CLS) dinamis pada entitas `Customers`. Buat kondisi di mana atribut `Customers.customerName` ditampilkan secara plain-text untuk pengguna dengan role `OPERATIONS`, namun otomatis di-masking menjadi `CONCAT(SUBSTRING(customer_name, 1, 2), '***')` jika dikonsumsi oleh pengguna dengan role `ANALYST_EXTERNAL`.

---

### 14. Challenge

**Skenario Kasus:** Anda adalah Lead Architect pada platform SaaS rantai pasok global. Sistem Anda melacak metrik inventaris:
- Metrik: `DailyEndingInventorySnapshot`
- Karakteristik: **Non-additive across time, semi-additive across locations**. Anda tidak dapat menjumlahkan stok hari Senin dan Selasa untuk mendapatkan stok mingguan; Anda harus mengambil nilai stok pada hari terakhir periode yang dipilih (Snapshot at Period End).
- Skala Data: 50.000 gudang, 200.000 SKU, pembaruan status setiap 5 menit (mencapai ~4 miliar baris per kuartal).

**Instruksi Tugas:**
1. Rancang model representasi semantik untuk menangani metrik semi-aditif ini secara deklaratif.
2. Jelaskan mekanisme Query Planner untuk mencegah eksekusi operasi `SUM()` sederhana pada rentang tanggal, melainkan secara otomatis mentranslasikannya menjadi *Last Value Window Function* atau *Point-in-Time Subquery*.
3. Susun arsitektur pre-agregasi yang memungkinkan analitik inventaris mingguan dan bulanan dipanggil dalam latensi di bawah 500 milidetik tanpa merusak konsistensi status fisik stok gudang.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konseptual & Dasar (5 Soal)
1. **Apa perbedaan mendasar antara definisi metrik di Semantic Layer dibanding view fisik di database?**
   - A. View database tidak mendukung operasi join.
   - B. Semantic Layer memisahkan metadata logika dari database fisik dan mendukung routing kueri serta caching dinamis multi-interface.
   - C. Semantic layer selalu berjalan di dalam memori web browser.
   - D. View database tidak bisa diindeks.
2. **Kapan kondisi "Chasm Trap" terjadi dalam pemodelan data relasional/semantik?**
   - A. Saat dua tabel fakta digabungkan melalui satu tabel dimensi konform, menyebabkan duplikasi kalkulasi saat agregasi.
   - B. Saat primary key bernilai NULL.
   - C. Saat kueri dijalankan tanpa klausa LIMIT.
   - D. Saat pre-agregasi kehabisan ruang disk.
3. **Apa arti istilah *Query Pushdown* dalam arsitektur semantic engine?**
   - A. Menarik seluruh data ke memori semantic layer sebelum difilter.
   - B. Menyerahkan komputasi agregasi, pemfilteran, dan join ke mesin pemrosesan data target (Lakehouse/OLAP).
   - C. Mengirimkan data langsung ke browser pengguna tanpa pengolahan.
   - D. Menurunkan prioritas thread kueri di level sistem operasi.
4. **Apa fungsi utama komponen *Abstract Syntax Tree* (AST) pada Semantic Engine?**
   - A. Menyimpan riwayat perubahan kode Git.
   - B. Memodelkan pohon struktur hierarki kueri semantik sebelum ditranslasikan menjadi sintaks SQL dialek tertentu.
   - C. Mengompresi penyimpanan file database fisik.
   - D. Menyediakan visualisasi dashboard real-time.
5. **Bagaimana penanganan Row-Level Security (RLS) pada arsitektur Headless Semantic Layer?**
   - A. Dikonfigurasi secara manual pada masing-masing dashboard analitik.
   - B. Mengabaikan hak akses pengguna dan mengandalkan firewall server.
   - C. Diinjeksi secara terpusat oleh engine ke dalam relasi kueri SQL berdasarkan konteks identitas (JWT/Session).
   - D. Dilakukan dengan menghapus baris data yang dilarang dari database utama.

#### Bagian B: Analisis & Menengah (5 Soal)
6. **Mengapa penambahan dimensi dengan kardinalitas sangat tinggi (seperti UUID unik) ke dalam tabel pre-agregasi dianggap sebagai anti-pattern?**
   - A. Menyebabkan query compiler error seketika.
   - B. Menghilangkan manfaat kompresi dan agregasi data, memicu ukuran tabel rollup membengkak menyamai tabel fakta mentah (*partition explosion*).
   - C. Mencegah penggunaan filter tanggal.
   - D. Memaksa engine mengubah dialect SQL secara otomatis.
7. **Sebuah kueri semantik meminta `Weekly Active Users` (WAU) dengan menghitung `COUNT(DISTINCT user_id)`. Mengapa metrik ini tidak dapat langsung diakumulasikan dari pre-agregasi `Daily Active Users`?**
   - A. Nilai distinct count bersifat non-additive; pengguna yang aktif di beberapa hari dalam satu minggu akan dihitung berulang.
   - B. Tipe data tanggal tidak kompatibel.
   - C. Operasi `COUNT(DISTINCT)` dilarang di semua platform OLAP modern.
   - D. Engine semantic hanya mendukung agregasi `SUM` dan `AVG`.
8. **Teknik optimasi apa yang digunakan semantic layer saat mengeksekusi metrik `COUNT(DISTINCT)` berskala miliaran baris dengan toleransi kesalahan 1-2% guna menghemat memori?**
   - A. B-Tree scan.
   - B. HyperLogLog (HLL) sketching algorithm pushdown.
   - C. Full table export ke CSV.
   - D. Brute-force map reduce.
9. **Dalam deployment zero-downtime semantic model, bagaimana engine mengelola pergantian schema pre-agregasi saat struktur baru dirilis?**
   - A. Menghapus tabel lama seketika dan membiarkan kueri pengguna gagal sementara.
   - B. Melakukan *blue-green refresh*: membangun tabel pre-agregasi versi baru di background, lalu mengalihkan pointer baca (*atomic pointer swap*) setelah sinkronisasi tuntas.
   - C. Mematikan database warehouse selama 1 jam.
   - D. Mengubah seluruh tipe data menjadi VARCHAR.
10. **Ketika mengintegrasikan Autonomous Agent (LLM) dengan Semantic Layer API, pendekatan mana yang paling aman dan akurat?**
    - A. Membiarkan LLM menghasilkan script DDL untuk membuat tabel baru secara bebas.
    - B. LLM mengeksekusi kueri langsung via koneksi root database database tanpa RLS.
    - C. LLM hanya memilih metrik dan dimensi dari katalog semantik terdaftar; eksekusi kueri ditangani oleh engine semantik dengan menyertakan token otentikasi pengguna penanya.
    - D. Memberikan seluruh skema DDL fisik 500 tabel kepada context window prompt LLM.

#### Bagian C: Skenario Kasus Produksi (3 Soal)
11. **Skenario Kasus 1:**
    Sebuah platform ride-hailing memproses 100 juta record perjalanan per hari. Tim operasional membutuhkan visualisasi rasio `cancelled_rides / total_rides` per area zona kota per jam. Namun, setiap hari Minggu pukul 23:59, sistem melambat secara drastis hingga kueri mengalami *timeout* (60 detik). 
    *Investigasi menemukan:* Partisi pre-agregasi dikonfigurasi dengan `granularity: 'day'` dan refresh window `update_window: '30 day'`.
    *Solusi perbaikan mana yang paling tepat untuk mengeliminasi bottleneck tersebut?*
    - A. Matikan seluruh pre-agregasi dan jalankan query pushdown langsung ke tabel mentah.
    - B. Naikkan timeout gateway menjadi 10 menit.
    - C. Ubah strategi pre-agregasi menjadi partisi harian independen (`partition_granularity: 'day'`) dan batasi interval update window inkremental hanya untuk 2 hari terakhir, disertai penjadwalan rebuild di luar jam puncak.
    - D. Mengubah database ke database dokumen berbasis NoSQL.

12. **Skenario Kasus 2:**
    Perusahaan e-commerce meluncurkan metrik semantik baru: `Customer Lifetime Value` (LTV). Ketika Tim Marketing membuka dashboard metrik tersebut melalui Tableau, angka LTV bernilai \$1.200 per user. Pada saat yang sama, tim internal Finance melihat angka LTV sebesar \$450 per user melalui internal admin portal.
    *Setelah ditelusuri:* Finance menggunakan filter `exclude_refunds = true` dan `include_tax = false`, sementara Tableau terhubung via konektor direct SQL yang tidak menyertakan filter tersebut.
    *Langkah rekayasa apa yang harus diambil untuk menyelesaikan akar masalah ini secara permanen?*
    - A. Kirimkan memo internal meminta tim marketing untuk menyalin query SQL tim Finance.
    - B. Tutup port direct SQL ke database; paksa koneksi Tableau menggunakan Semantic Layer JDBC/ODBC Driver yang merujuk pada metrik `customer_ltv` tunggal yang telah didefinisikan secara kanonikal.
    - C. Mengurangi hak akses tim Finance ke database.
    - D. Membuat tabel static baru yang di-refresh secara manual setahun sekali.

13. **Skenario Kasus 3:**
    Dalam audit kepatuhan privasi (GDPR/APPI), ditemukan bahwa sebuah query ad-hoc yang dieksekusi oleh data analyst tingkat junior berhasil mengekstrak nilai total gaji (`salary_expense`) per departemen di mana salah satu departemen hanya terdiri dari 1 orang karyawan (sehingga gaji individu karyawan tersebut terekspos secara langsung).
    *Mekanisme semantic governance apa yang harus diimplementasikan pada Semantic Layer untuk mencegah insiden ini?*
    - A. Menghapus data gaji dari data lakehouse.
    - B. Menerapkan *Differential Privacy* atau aturan *Aggregation Thresholding (k-anonymity)* pada engine semantik, di mana nilai agregasi otomatis dikaburkan atau ditolak jika jumlah entitas pembentuk (`COUNT(employee_id)`) berada di bawah batas minimum (misal: `< 5`).
    - C. Mewajibkan data analyst menandatangani formulir persetujuan non-disclosure baru.
    - D. Mematikan fitur group by pada dimensi departemen.

---

### Kunci Jawaban & Pembahasan Singkat Quiz

#### Bagian A: Dasar
1. **B** - Semantic layer menyatukan logika metrik bisnis di luar dependensi fisik database dan mengelola kueri serta cache secara otonom.
2. **A** - Chasm trap terjadi saat agregasi dilakukan melintasi beberapa tabel fakta yang memiliki relasi many-to-one ke tabel dimensi yang sama, memicu ledakan perkalian baris hasil *Cartesian product*.
3. **B** - Query pushdown memastikan pengolahan data volume besar tetap dieksekusi oleh mesin penyimpanan/warehouse berkinerja tinggi, bukan diproses lambat di aplikasi middleware.
4. **B** - AST memetakan struktur kueri logis secara formal sehingga dapat divalidasi, dioptimasi, dan diterjemahkan menjadi dialek SQL spesifik.
5. **C** - RLS dieksekusi secara native oleh engine semantik dengan menyuntikkan filter keamanan secara dinamis berdasarkan payload sesi pengguna.

#### Bagian B: Menengah
6. **B** - Pre-agregasi bekerja dengan memanfaatkan kompresi kelompok dimensi. Memasukkan atribut unik berkardinalitas tinggi menghancurkan rasio agregasi dan memboroskan penyimpanan.
7. **A** - Nilai Distinct Count tidak memiliki sifat komutatif-aditif antar interval waktu yang berbeda karena entitas yang sama dapat muncul di banyak hari.
8. **B** - HyperLogLog menggunakan probabilistic data structures untuk mengestimasi kardinalitas unik dengan penggunaan memori yang statis dan sangat efisien.
9. **B** - Arsitektur zero-downtime mewajibkan pembuatan tabel versi baru secara terpisah sebelum memindahkan pointer rujukan agar kueri baca tidak mengalami kegagalan/gangguan.
10. **C** - Pendekatan teraman adalah membatasi LLM hanya pada abstraksi metadata dan meneruskan hak otorisasi pengguna secara ketat melalui runtime semantic engine.

#### Bagian C: Kasus Produksi
11. **C** - Mengurangi scope rolling update window dan mempartisi pre-agregasi secara granular mencegah operasi *full historical rebuild* yang membebani resource saat transisi periode.
12. **B** - Masalah metrik ganda diselesaikan secara struktural dengan mengharuskan seluruh konsumsi analitik melewati kontrak semantik yang sama melalui protokol interface terstandarisasi.
13. **B** - Aggregation Thresholding / k-Anonymity pada level semantic mencegah kebocoran informasi individu yang terisolasi dalam grup agregasi berukuran kecil.

---

### 16. Summary

Implementasi Enterprise Business Intelligence modern telah bergeser dari arsitektur *BI-monolithic* menuju **Decoupled Headless Semantic Layer**. Pendekatan ini memisahkan secara tegas antara data warehousing fisik, standardisasi metrik, dan aplikasi konsumsi hilir.

Dengan menerapkan engine semantik:
- **Konsistensi Metrik Bisnis** terjaga secara mutlak di seluruh organisasi; metrik krusial hanya memiliki satu definisi kanonikal yang tersimpan di dalam repositori source-code terkontrol.
- **Kinerja Skala Besar** terjamin melalui translasi AST otomatis, *multi-pass query resolution* (mencegah *fan/chasm traps*), dan *two-tier pre-aggregation* bertingkat yang memangkas latensi kueri ke skala sub-detik.
- **Keamanan & Tata Kelola Zero-Trust** dapat ditegakkan di layer data paling awal, memastikan kebijakan RLS dan CLS berjalan otomatis tanpa bergantung pada dashboard pihak ketiga.
- **Kesiapan Otomasi AI**: Semantic Layer menyediakan *guardrail* berbasis konteks yang valid bagi Autonomous Agents dan Text-to-SQL workflows, mencegah halusinasi struktur database dan mengamankan eksekusi data analitik enterprise.