# Kurikulum Enterprise: AI & Data Product Management
## BAB 08: Go-To-Market Strategy & Product-Led Growth (PLG)
### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi PLG untuk AI-Native Products

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Technical Product Manager (TPM) dan Product Leader diharapkan mampu:
- Merancang dan memvalidasi arsitektur telemetri produk AI end-to-end untuk mengidentifikasi *Aha! Moment* dan *Product Qualified Leads* (PQL) secara deterministik.
- Mengimplementasikan pipeline Reverse-ETL dan Event-Driven Analytics guna menyinkronkan metrik inferensi model machine learning ke CRM (Salesforce/HubSpot) dan Customer Data Platform (CDP).
- Membangun sistem *Dynamic Entitlement Engine* dan *Usage-Based Metering* (UBB) terdistribusi yang memitigasi risiko latensi inferensi serta pembengkakan margin kotor (*Gross Margin Erosion*).
- Menghitung metrik unit economics GTM lanjutan: *CAC Payback Period*, *Net Revenue Retention* (NRR), *Token Burn Rate per PQL*, dan *Gross Margin Adjusted CAC*.
- Mengorkestrasikan strategi transisi *Self-Serve to Enterprise Sales-Assist* berbasis sinyal konsumsi inferensi (*Inference-Led Expansion*).

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- **Arsitektur Distributed Systems Dasar**: Konsep Message Broker (Apache Kafka/RabbitMQ), Relational vs NoSQL DB, dan API Gateway.
- **AI Infrastructure & Cost Drivers**: LLM Inference Lifecycle, Tokenomics (Input/Output/Cached Tokens), GPU profiling sederhana, dan batasan Concurrency/Rate-Limiting.
- **Dasar-dasar Analisis Data**: Intermediate SQL (Window Functions, Common Table Expressions/CTE, Data Aggregations).
- **Fundamental GTM & PLG**: Product Market Fit (PMF), Funnel AARRR (Acquisition, Activation, Retention, Revenue, Referral), serta perbedaan model Sales-Led Growth (SLG) vs Product-Led Growth (PLG).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi PLG pada produk AI-Native (misalnya: enterprise autonomous workflow automation, generative code analysis, AI doc-processing) memiliki tantangan fundamental yang tidak ditemukan pada SaaS tradisional: **Cost of Goods Sold (COGS) variabel yang melekat pada setiap interaksi produk**. 

Jika SaaS tradisional memiliki *marginal cost of serving an additional user* mendekati nol, AI-Native SaaS memiliki *compute cost per inference* yang signifikan. Kegagalan membangun arsitektur PLG terukur akan memicu *uncontrolled token consumption* oleh *free tier abusers*, membebani *gross margin*, dan mendistorsi metrik PQL.

```
       +---------------------------------------------------------------------------------------+
       |                                CLIENT APPLICATION                                     |
       +---------------------------------------------------------------------------------------+
                |                                                  ^                    |
       Telemetry Events                                            | Token Burn         | Feature
       (Segment Spec)                                              | Entitlements       | Access Req
                v                                                  | Checking           v
+-------------------------------+                       +-------------------+   +--------------------+
|  Telemetry Ingestion Pipeline |                       | Dynamic Feature   |   | Token Metering &   |
|  (Kafka -> ClickHouse/Snowflk)|                       | Flag / Entitlement|   | Billing Engine     |
+-------------------------------+                       | Engine (LaunchDk) |   | (Lago / Stripe)    |
                |                                       +-------------------+   +--------------------+
                v                                                  ^                    ^
+-------------------------------+                                  |                    |
| Real-time Scoring / Feature   |                                  |                    |
| Store (Feast / Redis)         |                                  |                    |
+-------------------------------+                                  |                    |
                |                                                  |                    |
                | Batch / Stream Inference                         | Sync Rules         | Webhook
                v                                                  |                    | Settlement
+-------------------------------+        Reverse-ETL      +------------------------------------------+
| Enterprise Data Warehouse     | ----------------------> | GTM Hub (Salesforce / HubSpot / Vitally) |
| (Snowflake / BigQuery / dbt)  |  (Census / Hightouch)   | -> Signals Sales-Assist rep if PQL Score |
+-------------------------------+                         +------------------------------------------+
```

#### Komponen Arsitektur Inti:
1. **Telemetry & Inference Instrumentation Layer**:
   Mencatat dua kategori data: *Product Behavior Telemetry* (klik UI, navigasi, konfigurasi alur kerja) dan *Inference Telemetry* (model ID, prompt token count, completion token count, cache hit ratio, latency milidetik, TTFT/Time to First Token, dan user prompt context).
2. **Real-time Entitlement & Rate-Limiter**:
   Layanan proxy dengan latensi rendah (low-latency proxy) di layer API Gateway yang memvalidasi *quota limit*, *credit balance*, dan *feature flags* pengguna sebelum mengizinkan komputasi GPU/LLM berjalan.
3. **Usage-Based Metering Engine**:
   Menghitung agregasi multi-dimensi secara deterministik (idempotent event consumption). Sistem ini mengonversi konsumsi infrastruktur (vCPU-hours, input/output tokens, storage vector) menjadi unit moneter yang dapat ditagihkan.
4. **PQL Scoring Engine & Reverse-ETL Pipeline**:
   Mesin analitik yang mengeksekusi model klasifikasi PQL (regresi logistik atau Gradient Boosting) berdasarkan interaksi gabungan (Product Signals + Inference Velocity). Data ini dikembalikan secara otomatis (*reverse-engineered*) ke CRM tim penjualan enterprise via Reverse-ETL.

---

### 4. Why & What

| Dimensi | Traditional SaaS PLG | AI-Native Enterprise PLG |
| :--- | :--- | :--- |
| **Marginal Cost of Free-Tier** | Mendekati $0.00 (Infrastruktur web standar). | Terikat langsung pada compute GPU/LLM API calls ($0.001 - $0.05+ per invocation). |
| **Value Verification Metric** | Daily/Monthly Active Users (DAU/MAU), Feature Clicks. | *Task Automation Completion Rate*, *Inference Success Yield*, *Latency-Adjusted Utility*. |
| **Activation Point (Aha!)** | Menyelesaikan onboarding wizard atau setup workspace. | Keberhasilan agentik pertama: Autonomous task selesai dengan akurasi terverifikasi manusia. |
| **Monetization Mechanics** | Flat Per-Seat / Per-User Subscription bulanan. | Hybrid: Base Platform Fee + Metered Usage Credit Tranches (Token, API invocations, CPU/GPU runtime). |
| **PQL Identification Signal** | Frekuensi login, jumlah rekan tim yang diundang (seat expansion). | *Consumption Acceleration Rate* (dC/dt), Runaway token consumption, Workspace-level GPU resource saturation. |

#### Urgensi bagi Technical PM:
Tanpa integrasi mendalam antara arsitektur rekayasa perangkat lunak dan strategi GTM, sebuah produk AI berisiko tinggi mengalami:
- **"Death by Free Trial"**: Gross Margin ambruk hingga negatif akibat eksploitasi inference tier gratisan.
- **"False PQL Trap"**: Menganggap pengguna yang membakar banyak token otomatis siap membeli paket enterprise, padahal lonjakan token terjadi karena loop tak terbatas (*infinite autonomous prompt loops*) atau integrasi webhook yang salah sasaran.

---

### 5. How (Workflow Detail)

Alur kerja operasional transisi prospek dari *Anonymous Visitor* menjadi *Enterprise Contract* melalui jalur PLG:

```
[User Sign-up via Self-Serve]
             |
             v
[Allocated Free Tier Credits: e.g., $10 Token Credit, Strict Concurrency Rate Limit: 2 Req/sec]
             |
             v
[Active Usage: User configures Autonomous Scraping & Analysis Agent]
             |
             +---> Telemetry Pipeline: Log Event `AgentExecutionCompleted`
             |     - Inputs: run_time_sec, tokens_used, error_rate, workflow_depth
             |
             v
[Threshold Evaluation Engine (Stream processing via Flink / dbt Core)]
             |
             |---> Did user hit Aha! Moment? (e.g., Completed >= 3 workflows with < 5% error in 48h)
             |           |
             |           +---> NO: Trigger In-App Guided Micro-Intervention via Agentic Assistance
             |           |
             |           +---> YES: Mark user state as ACTIVATED
             |
             v
[PQL Score Computation]
             |
             |---> Factors: Token burn acceleration (>50% MoM), Team members added (>= 3),
             |              Single-Domain Email match to Enterprise Database (Clearbit/ZoomInfo enrichment)
             |
             +---> Is PQL Score >= 85/100?
                         |
                         +---> NO: Maintain automated PLG nurture loop (Self-serve upgrade prompt)
                         |
                         +---> YES: Mark Account as "Product Qualified Account" (PQA)
                                     |
                                     v
                        [Trigger Reverse-ETL Sync]
                                     |
                                     +---> Update CRM (HubSpot/Salesforce): Assign Enterprise SDR
                                     +---> Fire Slack Alert to #enterprise-gtm-deals
                                     +---> Enable Soft-Limit Override on workspace (Grace capacity)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional Berbasis Konsumsi Bahan Bakar
Bayangkan produk Anda adalah layanan penyewaan jet pribadi (AI Agent). 
- **Traditional SaaS** seperti tiket masuk lounge bandara: Sekali bayar, makan sepuasnya, biaya marginal penyedia lounge untuk setiap croissant tambahan sangat rendah.
- **AI-Native PLG** adalah mengizinkan calon klien menerbangkan jet secara gratis sejauh 500 kilometer pertama (*Free Credit Tier*). Jika mereka hanya menerbangkan jet berputar-putar tanpa tujuan (prompt looping tanpa hasil), Anda merugi bahan bakar (GPU Compute) tanpa potensi konversi. 
- Namun, jika mereka menerbangkan jet itu untuk mengangkut kargo logistik bisnis nyata (*High Value Business Task*) dan mendarat tepat waktu, Anda tahu mereka adalah korporasi raksasa (*PQL*). Anda segera mengirimkan tim Sales-Assist ke landasan pacu sebelum bahan bakar gratisnya habis untuk menawarkan kontrak korporasi jangka panjang dengan jaminan armada khusus.

#### Detail Diagram Arsitektur Telemetri & Reverse-ETL:
```
+---------------------------------------------------------------------------------------------------+
| APPLICATION SERVICE LAYER                                                                         |
|                                                                                                   |
|  [FastAPI / Node Engine]                                                                          |
|       |                                                                                           |
|       +--- (Async Worker Event) ---> [Kafka Topic: 'agent-inference-telemetry']                   |
+---------------------------------------------------|-----------------------------------------------+
                                                    |
                                                    v
+---------------------------------------------------------------------------------------------------+
| STREAM INGESTION & DATA LAKE LAYER                                                                |
|                                                                                                   |
|  [Vector / ClickHouse Ingest] <--- (Schema Validation via Avro / Protobuf)                        |
|       |                                                                                           |
|       +---> ClickHouse Raw Telemetry Table (`inference_logs`)                                     |
|                  |                                                                                |
|                  +---> Materialized View: `hourly_org_consumption`                                |
+---------------------------------------------------|-----------------------------------------------+
                                                    |
                                                    v
+---------------------------------------------------------------------------------------------------+
| DATA WAREHOUSE & ANALYTICS LAYER                                                                  |
|                                                                                                   |
|  [Snowflake / Databricks]                                                                         |
|       |                                                                                           |
|       +--- (dbt Execution every 15 mins) ---> Generates `pql_scoring_view`                        |
|                                                    |                                              |
|       +--------------------------------------------+                                              |
|       | - org_id                                                                                  |
|       | - token_velocity_7d                                                                       |
|       | - task_success_rate                                                                       |
|       | - seat_activation_ratio                                                                   |
|       | - enriched_company_revenue                                                                |
|       | - computed_pql_tier (TIER_1, TIER_2, TIER_3)                                              |
+---------------------------------------------------|-----------------------------------------------+
                                                    |
                                                    v
+---------------------------------------------------------------------------------------------------+
| OPERATIONAL REVERSE-ETL & REVENUE ENGINE                                                          |
|                                                                                                   |
|  [Census / Hightouch Sync Engine]                                                                 |
|       |                                                                                           |
|       +---> [Salesforce/HubSpot API]                                                              |
|       |       - Action: Create Deal / Task for Strategic AE                                       |
|       |       - Context Payload: Top 3 workflows executed, current burn rate                      |
|       |                                                                                           |
|       +---> [Metering & Billing Gateway (Stripe/Lago)]                                            |
|               - Action: Auto-invoice threshold triggers or update tiered entitlement              |
+---------------------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example (Kode Standar Industri)

#### Simple Example: Perhitungan Metrik Unit Economics PLG AI-Native via Python
Sebagai TPM, Anda harus memantau apakah *Net Expansion* didorong oleh penggunaan token atau penambahan seat, serta menghitung *CAC Payback Period* yang disesuaikan dengan Gross Margin (karena beban GPU).

```python
def calculate_ai_plg_metrics(
    mrr_start: float,
    mrr_expansion_usage: float,
    mrr_expansion_seats: float,
    mrr_churned: float,
    gross_margin_percentage: float,
    total_sales_marketing_cost: float,
    new_customers_acquired: int
) -> dict:
    """
    Menghitung metrik fundamental PLG untuk produk berbasis kecerdasan buatan.
    """
    # Net Retention Rate (NRR) Formula
    mrr_end = mrr_start + mrr_expansion_usage + mrr_expansion_seats - mrr_churned
    nrr = ((mrr_start + mrr_expansion_usage + mrr_expansion_seats - mrr_churned) / mrr_start) * 100
    
    # Customer Acquisition Cost (CAC)
    cac = total_sales_marketing_cost / new_customers_acquired if new_customers_acquired > 0 else 0.0
    
    # Blended Monthly Revenue per New Customer
    avg_mrr_per_customer = (mrr_end / new_customers_acquired) if new_customers_acquired > 0 else 0.0
    
    # CAC Payback Period (Adjusted for Gross Margin)
    # Payback (Months) = CAC / (ARPU * Gross Margin %)
    margin_adjusted_arpu = avg_mrr_per_customer * (gross_margin_percentage / 100.0)
    cac_payback_months = (cac / margin_adjusted_arpu) if margin_adjusted_arpu > 0 else float('inf')

    return {
        "NRR_Percentage": round(nrr, 2),
        "CAC_USD": round(cac, 2),
        "Gross_Margin_Adjusted_Payback_Months": round(cac_payback_months, 2),
        "Usage_vs_Seat_Expansion_Ratio": round(mrr_expansion_usage / mrr_expansion_seats, 2) if mrr_expansion_seats > 0 else None
    }

# Evaluasi skenario produksi
metrics = calculate_ai_plg_metrics(
    mrr_start=100000.0,
    mrr_expansion_usage=25000.0,
    mrr_expansion_seats=5000.0,
    mrr_churned=4000.0,
    gross_margin_percentage=55.0, # Margin tertekan biaya compute LLM
    total_sales_marketing_cost=150000.0,
    new_customers_acquired=30
)

print(metrics)
# Output: {'NRR_Percentage': 126.0, 'CAC_USD': 5000.0, 'Gross_Margin_Adjusted_Payback_Months': 21.67, 'Usage_vs_Seat_Expansion_Ratio': 5.0}
```

#### Practical Example: Model Data DBT (SQL) untuk Scoring PQL Berbasis Telemetri Token & Retensi
Model SQL ini berjalan di dbt/Snowflake untuk mengekstrak data dari data lakehouse dan mengidentifikasi kapan sebuah *organization* mencapai kriteria **Product Qualified Account (PQA)** untuk disinkronkan ke CRM.

```sql
-- models/marts/gtm/pqa_high_propensity_leads.sql

WITH daily_org_usage AS (
    SELECT
        organization_id,
        DATE(event_timestamp) AS usage_date,
        COUNT(DISTINCT session_id) AS active_sessions,
        COUNT(DISTINCT user_id) AS active_users,
        SUM(prompt_tokens + completion_tokens) AS total_tokens_consumed,
        SUM(estimated_cost_usd) AS estimated_inference_cost,
        SUM(CASE WHEN execution_status = 'SUCCESS' THEN 1 ELSE 0 END)::FLOAT / 
            NULLIF(COUNT(task_id), 0) AS task_completion_rate
    FROM {{ ref('stg_telemetry_inference_events') }}
    WHERE event_timestamp >= CURRENT_DATE - INTERVAL '30 DAYS'
    GROUP BY 1, 2
),

aggregated_metrics AS (
    SELECT
        organization_id,
        COUNT(DISTINCT usage_date) AS days_active_last_30,
        AVG(total_tokens_consumed) AS avg_daily_tokens,
        SUM(total_tokens_consumed) AS total_tokens_30d,
        AVG(task_completion_rate) AS avg_success_rate,
        MAX(active_users) AS peak_active_users,
        -- Mengukur akselerasi konsumsi 7 hari terakhir vs 30 hari
        COALESCE(
            SUM(CASE WHEN usage_date >= CURRENT_DATE - INTERVAL '7 DAYS' THEN total_tokens_consumed ELSE 0 END) / 
            NULLIF(SUM(CASE WHEN usage_date < CURRENT_DATE - INTERVAL '7 DAYS' THEN total_tokens_consumed ELSE 0 END), 0),
            0
        ) AS token_velocity_ratio
    FROM daily_org_usage
    GROUP BY 1
),

firmographic_data AS (
    SELECT
        org_id,
        company_name,
        domain,
        employee_count,
        industry,
        current_plan_tier
    FROM {{ ref('dim_organizations') }}
)

SELECT
    f.org_id,
    f.company_name,
    f.domain,
    f.current_plan_tier,
    a.days_active_last_30,
    a.total_tokens_30d,
    a.token_velocity_ratio,
    a.avg_success_rate,
    a.peak_active_users,
    -- PQL Score Computation (Scale 0 - 100)
    LEAST(100, ROUND(
        (CASE WHEN f.employee_count > 250 THEN 25 ELSE 10 END) +
        (CASE WHEN a.token_velocity_ratio > 1.5 THEN 25 ELSE 10 END) +
        (CASE WHEN a.avg_success_rate > 0.85 THEN 25 ELSE 5 END) +
        (CASE WHEN a.peak_active_users >= 5 THEN 25 ELSE 5 END)
    )) AS pql_score,
    CURRENT_TIMESTAMP AS calculated_at
FROM aggregated_metrics a
INNER JOIN firmographic_data f ON a.organization_id = f.org_id
WHERE f.current_plan_tier IN ('FREE_TIER', 'STARTER_SELF_SERVE')
  AND a.days_active_last_30 >= 5
HAVING pql_score >= 75
ORDER BY pql_score DESC;
```

#### Production Webhook Handler: Reverse-ETL / Rate-Limit Event Dispatcher (Node.js/TypeScript)
Contoh kode backend gateway untuk menangani sinyal exhaustion kredit secara gracefully tanpa memutus pipeline bisnis pengguna, sembari memicu Sales-Assist loop.

```typescript
// src/gateways/entitlements/consumptionWebhook.ts

import { Request, Response } from 'express';
import { Redis } from 'ioredis';
import { SalesCloudClient } from '../integrations/salesforce';
import { MetricsLogger } from '../monitoring/logger';

const redis = new Redis(process.env.REDIS_CLUSTER_URL);
const salesforce = new SalesCloudClient(process.env.SF_AUTH_TOKEN);

interface UsagePayload {
  organizationId: string;
  consumedCredits: number;
  allocatedCredits: number;
  currentVelocityPerHour: number;
}

export const handleQuotaThresholdExceeded = async (req: Request, res: Response): Promise<void> => {
  const { organizationId, consumedCredits, allocatedCredits, currentVelocityPerHour }: UsagePayload = req.body;

  try {
    const percentageUsed = (consumedCredits / allocatedCredits) * 100;
    MetricsLogger.info(`Evaluating quota limits for org: ${organizationId}`, { percentageUsed });

    if (percentageUsed >= 80 && percentageUsed < 100) {
      // Step 1: Pasang idempotency key di Redis untuk mencegah multi-trigger alert
      const alertLockKey = `lock:soft_limit_alert:${organizationId}`;
      const isLocked = await redis.set(alertLockKey, 'active', 'EX', 86400, 'NX');

      if (isLocked) {
        // Step 2: Kirim telemetry notification ke GTM Slack Channel & update CRM
        await salesforce.updateLeadOpportunity(organizationId, {
          stage: 'Consumption Risk / Upsell Opportunity',
          notes: `Workspace reached ${percentageUsed.toFixed(1)}% usage. Velocity: ${currentVelocityPerHour} credits/hr.`
        });

        // Step 3: Aktifkan graceful overflow buffer (15% grace threshold) agar pipeline inferensi tidak crash
        await redis.set(`entitlement:grace_buffer:${organizationId}`, 'true', 'EX', 172800);
      }
    } else if (percentageUsed >= 100) {
      // Verifikasi apakah grace buffer aktif
      const hasGrace = await redis.get(`entitlement:grace_buffer:${organizationId}`);
      
      if (!hasGrace) {
        // Hard cutoff jika grace buffer habis atau tidak aktif
        await redis.set(`entitlement:execution_blocked:${organizationId}`, 'true');
        res.status(402).json({
          error: 'QUOTA_EXHAUSTED',
          message: 'Workspace credit limit exceeded. Upgrade to Enterprise Plan to unblock concurrency.',
          cta_url: 'https://app.company.ai/billing/upgrade'
        });
        return;
      }
    }

    res.status(200).json({ status: 'PROCESSED', organizationId });
  } catch (error) {
    MetricsLogger.error('Failed to process usage webhook', error);
    res.status(500).json({ error: 'INTERNAL_ERROR' });
  }
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: "ScribeFlow.ai" (AI Enterprise Document Workflow)
* **Konteks**: Platform pemrosesan dokumen otomatis berbasis multimodal LLM untuk perbankan dan asuransi. Model bisnis beralih dari Enterprise Direct Sales murni ke Hybrid Product-Led Growth (Freemium dengan $50 token credit gratis per bulan).
* **Masalah**:
  1. *GPU Cost Runaway*: Dalam 3 bulan pertama, tagihan OpenAI & AWS Bedrock melonjak dari $40,000 menjadi $220,000/bulan.
  2. *Low Conversion*: Tingkat konversi Free-to-Paid di bawah 0.8%. Tim sales menghubungi ribuan *lead* yang ternyata hanya mahasiswa atau peneliti yang mengunggah dokumen akademis secara massal (*bad fit users*).
  3. *Gross Margin Erosion*: Gross margin merosot drastis hingga 32% (standar enterprise SaaS adalah 70-80%).
* **Solusi Arsitektural & GTM oleh Tim Produk**:
  1. *Dual-Horizon Gatekeeper*: Menerapkan validasi domain korporasi ketat pada *sign-up*. Alamat email publik (Gmail/Yahoo) dibatasi pada model quantize kecil (open-source LLaMA 8B on CPU/inferensi murah) dan dibatasi maksimal 5 dokumen per hari.
  2. *Telemetry-Driven Aha! Metric*: Melalui analisis regresi logistik, TPM menemukan bahwa retensi 90 hari dan konversi enterprise terjadi **HANYA JIKA** sebuah organisasi mengunggah minimal 3 dokumen kompleks berformat sama, mengoreksi data < 2 kali, dan mengundang minimal 2 kolega dalam waktu 7 hari pertama (*Deterministic PQL*).
  3. *Inference-Led Sales Assist*: Membangun integrasi ClickHouse + Snowflake + Hightouch ke HubSpot. Begitu sebuah akun mencapai PQL threshold, tim Sales-Assist menerima profil ringkas:
     - Jenis dokumen yang sering diproses.
     - Estimasi jam kerja manual yang berhasil dihemat (*time-to-value calculation*).
     - Utilisasi token saat ini vs projected exhaustion date.
* **Hasil**:
  - Konversi Free-to-Paid Enterprise naik dari 0.8% menjadi 4.6%.
  - Gross Margin pulih kembali ke 68% karena alokasi LLM mahal terisolasi hanya untuk high-propensity leads.
  - CAC Payback Period terpangkas dari 28 bulan menjadi 9.4 bulan.

---

### 9. Trade-offs

Setiap keputusan arsitektur dalam pipeline PLG enterprise memiliki konsekuensi langsung pada skalabilitas teknis dan performa finansial:

| Keputusan Arsitektur | Keuntungan | Biaya & Kompromi (Trade-offs) |
| :--- | :--- | :--- |
| **Strict Hard Quotas** (Putus eksekusi seketika saat kredit habis) | Mencegah margin leakage 100%; pengeluaran LLM terkendali tanpa risiko *overdraft*. | Merusak User Experience. Workflow automasi bisnis misi-kritis pengguna akan mati di tengah jalan, meningkatkan potensi *churn*. |
| **Generous Grace Buffers** (Toleransi over-limit hingga 20%) | Pengalaman pengguna seamless; memberi waktu bagi Sales-Assist untuk bernegosiasi. | Risiko *uncollectible debt* (klien menolak membayar tagihan *overage* setelah trial). Membebani Working Capital perusahaan. |
| **Synchronous Real-Time Telemetry Check** | Pengecekan entitlement 100% presisi dan mencegah race-condition multi-request. | Menambahkan latensi 50-150ms pada setiap API inference invocation; rentan kegagalan *single-point-of-failure* jika engine meter down. |
| **Asynchronous Stream Metering** (Kafka/Flink Event-driven) | Zero-latency overhead pada user request path; arsitektur inferensi sangat cepat. | *Eventual consistency*: Ada jeda waktu (biasanya beberapa detik hingga menit) di mana user dapat mengonsumsi compute melampaui kuotanya (*metering drift*). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Mengukur Keberhasilan Onboarding Menggunakan Metrik Vanitas
* **Kesalahan**: Menganggap user yang login setiap hari (*DAU*) atau membuat 100 prompt adalah akun yang teraktivasi (*Activated Account*).
* **Solusi/Troubleshooting**: Validasi apakah prompt tersebut menghasilkan *successful downstream business outcome*. Ukur rasio *Task Completion vs Error Rate*. Pengguna yang me-regenerate respons 10 kali biasanya mengalami frustrasi produk, bukan menunjukkan keterikatan yang sehat.

#### 2. Ketiadaan Rate Limiting pada Level Organisasi (Workspace)
* **Kesalahan**: Hanya membatasi rate limit per user (misal: 60 req/min). Sebuah enterprise user mendaftarkan 50 akun trial bot dalam satu domain dan menjalankan distributed scraper yang menguras budget compute GPU Anda.
* **Solusi/Troubleshooting**: Terapkan *Hierarchical Token Bucket Rate Limiting* di API Gateway:
  1. Tingkat API Key / User.
  2. Tingkat Workspace / Organisasi.
  3. Tingkat Apex Domain (seluruh pengguna dengan domain `@targetcorp.com` berbagi satu *global trial pool*).

#### 3. Data Leakage pada Pipeline Reverse-ETL
* **Kesalahan**: Menyinkronkan prompt mentah (*raw user text/PII*) dari telemetry lakehouse langsung ke CRM Sales.
* **Solusi/Troubleshooting**: Sanitasi data di layer transformasi (dbt). CRM hanya boleh menerima data agregasi numerik dan kategorikal (misal: `monthly_tokens_consumed`, `primary_document_type`, `industry_vertical`), bukan data teks sensitif pengguna.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum meluncurkan self-serve onboarding atau hybrid GTM model untuk platform AI:

- [ ] **FinOps & Guardrails**:
  - [ ] Model rate-limiting per organisasi telah terpasang di layer API Gateway.
  - [ ] Circuit-breaker otomatis memutus pemanggilan foundation model jika daily burn rate melebihi budget alokasi trial ($X/hari).
  - [ ] Sistem peringatan terpasang pada PagerDuty jika gross margin mingguan jatuh di bawah ambang batas (misal: < 60%).
- [ ] **Telemetry & Analytics**:
  - [ ] Skema pelacakan (tracking schema) tervalidasi menggunakan schema registry (e.g., Protobuf/JSON Schema) untuk menghindari event data korup.
  - [ ] Metrik inferensi (Token Input, Token Output, Latency, Error Status) dipisahkan dari payload konten sensitif (PII sanitization).
  - [ ] Reverse-ETL sync berjalan otomatis minimal setiap 1-4 jam untuk menyegarkan skor PQL ke tim penjualan.
- [ ] **Billing & Entitlements**:
  - [ ] Tersedia mekanisme *soft-landing/grace capacity* (pengguna tidak di-block secara mendadak saat workflow bisnis penting berlangsung).
  - [ ] Webhook penagihan terintegrasi secara *idempotent* untuk menghindari double-billing pengguna atas token yang sama.
- [ ] **Sales-Assist Enablement**:
  - [ ] Data telemetri yang disinkronkan ke CRM mencantumkan metrik ROI yang jelas (e.g., "Menghasilkan 400 jam efisiensi kerja bulan ini") untuk materi negosiasi tim sales.

---

### 12. Hands-on Practice

Buat dan simpan file implementasi berikut di direktori `hands-on/m02/` pada environment pengembangan Anda.

#### Langkah 1: Siapkan Struktur Proyek
```bash
mkdir -p hands-on/m02/data
mkdir -p hands-on/m02/src
cd hands-on/m02
```

#### Langkah 2: Buat Dataset Simulasi Telemetri
Simpan file ini di `hands-on/m02/data/raw_inference_logs.csv`:
```csv
event_id,org_id,user_id,timestamp,model_used,input_tokens,output_tokens,status,task_type
evt_01,org_alpha,usr_1,2024-10-01T08:00:00Z,gpt-4o,1200,450,SUCCESS,data_extraction
evt_02,org_alpha,usr_1,2024-10-01T08:30:00Z,gpt-4o,3400,1200,SUCCESS,data_extraction
evt_03,org_alpha,usr_2,2024-10-02T09:00:00Z,gpt-4o,800,200,FAILED,classification
evt_04,org_beta,usr_3,2024-10-01T10:00:00Z,claude-3-5-sonnet,50000,4000,SUCCESS,agent_loop
evt_05,org_beta,usr_3,2024-10-01T11:00:00Z,claude-3-5-sonnet,65000,5000,SUCCESS,agent_loop
evt_06,org_beta,usr_3,2024-10-02T12:00:00Z,claude-3-5-sonnet,80000,7000,SUCCESS,agent_loop
evt_07,org_gamma,usr_4,2024-10-02T14:00:00Z,gpt-4o-mini,150,50,SUCCESS,summarization
```

#### Langkah 3: Eksekusi Pipeline Kalkulasi PQL & Margin Alerting
Tulis skrip analisis berikut di `hands-on/m02/src/pql_engine.py`:
```python
import pandas as pd
import json

# Konstanta Biaya Model per 1k Token (Pricing Benchmark)
PRICING_MATRIX = {
    'gpt-4o': {'input': 0.005 / 1000, 'output': 0.015 / 1000},
    'claude-3-5-sonnet': {'input': 0.003 / 1000, 'output': 0.015 / 1000},
    'gpt-4o-mini': {'input': 0.00015 / 1000, 'output': 0.0006 / 1000}
}

def run_pql_pipeline(csv_path: str):
    df = pd.read_csv(csv_path)
    
    # 1. Hitung direct compute cost per event
    def calculate_cost(row):
        rates = PRICING_MATRIX.get(row['model_used'], {'input': 0.001/1000, 'output': 0.002/1000})
        return (row['input_tokens'] * rates['input']) + (row['output_tokens'] * rates['output'])

    df['cost_usd'] = df.apply(calculate_cost, axis=1)

    # 2. Agregasi metrik per organisasi
    summary = df.groupby('org_id').agg(
        total_events=('event_id', 'count'),
        successful_events=('status', lambda x: (x == 'SUCCESS').sum()),
        total_tokens=('input_tokens', lambda x: x.sum() + df.loc[x.index, 'output_tokens'].sum()),
        total_spend_usd=('cost_usd', 'sum'),
        unique_users=('user_id', 'nunique')
    ).reset_index()

    summary['success_rate'] = summary['successful_events'] / summary['total_events']

    # 3. Kriteria Evaluasi PQL
    # Syarat PQL: Total spend > $0.50, Success Rate > 75%, Min 1 unique user
    def evaluate_pql(row):
        score = 0
        if row['total_spend_usd'] > 0.50:
            score += 40
        if row['success_rate'] >= 0.75:
            score += 30
        if row['unique_users'] > 1:
            score += 30
        return score

    summary['pql_score'] = summary.apply(evaluate_pql, axis=1)
    summary['sales_action_required'] = summary['pql_score'] >= 70

    # 4. Generate reverse-ETL payload output
    sync_payload = summary.to_dict(orient='records')
    print("--- REVERSE-ETL SYNC PAYLOAD GENERATED ---")
    print(json.dumps(sync_payload, indent=2))
    
    # Simpan hasil untuk validasi
    summary.to_csv('hands-on/m02/pql_eval_output.csv', index=False)
    print("\nFile berhasil disimpan di: hands-on/m02/pql_eval_output.csv")

if __name__ == '__main__':
    run_pql_pipeline('hands-on/m02/data/raw_inference_logs.csv')
```

Jalankan skrip:
```bash
python3 hands-on/m02/src/pql_engine.py
```

---

### 13. Exercise

#### Level: Easy
Sebuah produk AI transkripsi memiliki biaya inferensi LLM sebesar $0.02 per menit audio. Paket Self-Serve mengenakan biaya langganan tetap $30/bulan per user dengan jatah transkripsi maksimal 1,000 menit per bulan. 
- **Pertanyaan**: Hitung *Gross Margin %* terburuk dari seorang pengguna yang memaksimalkan seluruh kuota transkripsinya setiap bulan. Apakah skema pricing ini sehat untuk bisnis SaaS?

#### Level: Medium
Tuliskan satu kueri SQL analitik untuk mendeteksi *Runaway Loop Consumption*. Cari seluruh `workspace_id` di mana jumlah pemanggilan API dalam 1 jam terakhir melebihi 3x lipat rata-rata pemanggilan per jam selama 7 hari sebelumnya, dan memiliki tingkat kegagalan (*error status*) lebih dari 40%.

#### Level: Hard
Rancang State Machine (dalam format pseudocode atau diagram transisi status) untuk sistem *Entitlement Engine* yang menangani transisi status kuota pengguna: `NORMAL` $\to$ `APPROACHING_LIMIT` (80%) $\to$ `GRACE_PERIOD` (100%-115%) $\to$ `SUSPENDED` (>115%). 
- Sertakan penanganan kondisi ketika pengguna melakukan upgrade paket pembayaran instan saat berada di status `GRACE_PERIOD`.

---

### 14. Challenge

**Konteks Tantangan**: 
Anda adalah Principal TPM di sebuah platform agen AI coding otonom ("CodeBot.ai"). Produk Anda menawarkan model PLG Freemium di mana pengguna dapat menjalankan agen untuk mencari bug di repositori GitHub mereka. 

**Kondisi Krisis**:
1. Metrik pendaftaran (*Acquisition*) melonjak 400% bulan ini, namun Gross Margin anjlok dari 72% menjadi 18%.
2. Investigasi awal menunjukkan ada sindikat yang memanfaatkan trial CodeBot untuk menjalankan perbaikan kode pada ribuan repositori open-source berskala masif, membakar token tanpa pernah berkonversi ke Enterprise Tier.
3. Sementara itu, 15 calon prospek enterprise bernilai kontrak besar (Fortune 500) yang sedang mencoba trial mengeluhkan latensi eksekusi agen yang sangat lambat (*GPU queuing delay*) dan mempertimbangkan untuk membatalkan pilot project.

**Tugas Anda**:
Susun dokumen strategi rekayasa produk (Product Architecture Strategy Document) maksimal 3 halaman yang mencakup:
1. Desain **Multi-Tier Inference Throttle Architecture** yang memisahkan beban *unverified free users* dari *high-value corporate prospects* tanpa merusak konversi funnel organik.
2. Definisi ulang matriks **Product Qualified Account (PQA)** untuk mengidentifikasi prospek enterprise secara deterministik di < 48 jam pertama.
3. Rencana transisi penagihan dari *Pure Free Tier* menuju *Reverse-Trial with Credit Card Upfront vs Hybrid Metered Model*.
4. Rencana komunikasi dan mitigasi risiko reputasi publik pada komunitas developer open source.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. Apa perbedaan mendasar antara *Customer Acquisition Cost* (CAC) tradisional dengan *Gross Margin Adjusted CAC* pada produk AI-Native?
2. Mengapa metrik DAU/MAU tradisional sering kali menyesatkan jika dijadikan indikator utama PQL pada produk berbasis generative AI?
3. Sebutkan fungsi utama dari pipeline *Reverse-ETL* dalam arsitektur Product-Led Growth!
4. Apa yang dimaksud dengan *Token Velocity* dalam konteks scoring leads GTM?
5. Mengapa produk AI PLG membutuhkan mekanisme *Hierarchical Rate Limiting*?

#### Bagian 2: Intermediate (5 Soal)
6. Bagaimana cara mencegah terjadinya *race conditions* pada pencatatan konsumsi token ketika puluhan agen otonom berjalan secara bersamaan dalam satu organisasi?
7. Mengapa model *usage-based pricing* murni (pure pay-as-you-go) sering kali sulit diterima oleh bagian pengadaan (procurement) perusahaan enterprise berskala besar, dan bagaimana cara memitigasinya?
8. Dalam kondisi apa sebuah metrik *Task Completion Rate* yang tinggi justru merefleksikan kegagalan value delivery produk?
9. Jelaskan trade-off antara synchronous rate-limiting checking via In-Memory Cache (Redis) vs Asynchronous stream evaluation (Kafka/Flink) terhadap metrik user-perceived latency (TTFT)!
10. Formula apa yang paling tepat digunakan untuk mengukur efektivitas transisi dari *Self-Serve User* menjadi *Sales-Assisted Enterprise Contract*?

#### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario A (FinOps & Capacity)**: 
    Platform generative video Anda mengalami lonjakan penggunaan hingga 300% pada weekend akibat sebuah fitur viral di media sosial. Biaya compute GPU cloud Anda membengkak hingga $50,000 dalam 48 jam, namun 99% dari pengguna tersebut berasal dari disposable email yang tidak memiliki nilai LTV bisnis. Tindakan arsitektural dan operasional darurat apa yang harus segera Anda eksekusi dalam 2 jam pertama sebagai PM?

12. **Skenario B (Data Synchronization & Race Condition)**:
    Sistem Reverse-ETL Anda menyinkronkan status PQL ke Salesforce setiap 6 jam. Seorang prospek tier-1 (CTO bank multinasional) mendaftar, menghabiskan seluruh kuota trial dalam 1 jam, mengalami eksekusi terblokir (*hard limit*), dan langsung meninggalkan aplikasi karena frustrasi sebelum tim penjualan Anda menerima notifikasi lead PQL di Salesforce. Bagaimana Anda mendesain ulang sistem notifikasi dan arsitektur entitlements ini untuk mencegah insiden berulang?

13. **Skenario C (GTM Metric Conflict)**:
    VP of Sales menuntut agar seluruh pengguna yang telah menghabiskan kredit trial $100 otomatis dialihkan langsung ke tim SDR untuk ditutup kontrak enterprise-nya. Namun, data menunjukkan bahwa 60% dari akun-akun tersebut memiliki *task error rate* di atas 70% (pengguna frustrasi mencoba mengulang prompt yang gagal). Jika sales memaksa menghubungi mereka, tingkat konversi sales sangat rendah dan CSAT anjlok. Bagaimana Anda meredefinisi kriteria PQL di data warehouse untuk menyelaraskan target Sales dan Engineering?

---

### 16. Summary

1. **AI PLG Economics Berbeda Secara Fundamental**: Margin kotor produk AI-Native terikat langsung pada komputasi inferensi. Pendekatan PLG tanpa proteksi guardrails compute akan memicu kegagalan finansial (*Gross Margin Erosion*).
2. **Deterministic PQL Scoring**: Mengidentifikasi PQL pada era agen AI memerlukan konvergensi antara data *Product Telemetry* (klik, undang anggota tim), *Inference Performance* (keberhasilan penyelesaian alur tugas, token burn velocity), dan *Enriched Firmographics* (domain korporasi).
3. **Arsitektur Telemetri Terintegrasi**: Arsitektur modern memisahkan penanganan inferensi cepat di edge dengan pencatatan event asinkron via streaming bus (Kafka), dianalisis di Data Lakehouse (ClickHouse/Snowflake), dan didorong kembali ke CRM melalui Reverse-ETL untuk aksi proaktif Sales-Assist.
4. **Proteksi Entitlement yang Humanis**: Hindari hard-limit kaku yang merusak alur kerja kritis pengguna. Gunakan kombinasi *grace capacity buffers*, *hierarchical limits*, dan notifikasi otomatis multi-channel untuk mengubah batasan kuota menjadi momentum konversi penjualan korporat.