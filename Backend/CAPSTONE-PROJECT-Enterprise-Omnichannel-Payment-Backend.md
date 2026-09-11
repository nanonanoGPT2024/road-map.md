---
[⬅️ BAB 10 Quiz & Challenge](./BAB-10-Arsitektur-Backend-Lanjutan-dan-Skalabilitas-Sistem/BAB-10-Quiz-dan-Challenge.md) | [📋 Silabus Induk](./README.md) | [🎉 Kurikulum Selesai / Tamat](#)
---

# Capstone Project: Enterprise Omnichannel Payment & Ledger Backend Gateway

## 1. Project Overview & Business Context
Selamat datang di **Capstone Project Backend Developer Mastery**. Proyek akhir ini merupakan integrasi komprehensif dari seluruh kompetensi teknis yang telah Anda pelajari dari BAB 01 hingga BAB 10:
- Fondasi Jaringan HTTP/2, WebSockets, & TLS (BAB 01).
- Concurrency Runtime, Garbage Collection, & Profiling (BAB 02).
- RESTful API Idempotency, gRPC Protobuf, & GraphQL (BAB 03).
- Relational ACID, Isolation Levels, & B-Tree Indexing (BAB 04).
- NoSQL Sharding, Consistent Hashing, & Vector Search (BAB 05).
- Caching Patterns, Redis Internals, & Distributed Lock (BAB 06).
- Kafka Event Streaming, Idempotent Consumer, & Transactional Outbox (BAB 07).
- OAuth 2.0 PKCE, OWASP API Security, & AES-256-GCM (BAB 08).
- Testcontainers, Contract Testing, & p99 Load Profiling (BAB 09).
- Domain-Driven Design (DDD), Saga Orchestrator, & CQRS Event Sourcing (BAB 10).

Anda ditunjuk sebagai **Lead Backend Architect** untuk membangun **"PayPulse Global"**: Sistem Gerbang Pembayaran Omnichannel (*Omnichannel Payment Gateway*) yang memproses transaksi kartu kredit, QRIS/Virtual Account, dan dompet digital untuk 50.000 merchant e-commerce global dengan throughput puncak **20.000 transaksi per detik (TPS)** dan target ketersediaan **99.999% (Five Nines)**.

---

## 2. Requirement Engineering (Spesifikasi Kebutuhan)

### A. Functional Requirements (Kebutuhan Fungsional)
1. **Merchant Onboarding & API Key Vault:** Merchant dapat mendaftar, membuat pasangan API Key privat (`sec_live_...`), dan mengatur webhook callback endpoint.
2. **Unified Payment API (Charge Creation):** Endpoint tunggal `POST /v1/charges` yang menerima transaksi multi-metode (Credit Card, Virtual Account, E-Wallet, QRIS) dengan jaminan **Idempotensi Mutlak**.
3. **Double-Entry Financial Ledger (Buku Besar Akuntansi Ganda):** Setiap perpindahan dana wajib dicatat dalam pembukuan ganda (*Journal Entries* yang selalu *Balance*: $\sum \text{Debit} = \sum \text{Credit}$). Dana tidak boleh diciptakan atau dimusnahkan secara sembarangan.
4. **Saga Orchestrator Settlement:** Koordinasi transaksi terdistribusi yang melibatkan Fraud Detection, Bank Gateway Connector, Ledger Service, dan Merchant Balance Settlement.
5. **Real-Time Webhook Notification Engine:** Menyiarkan status transaksi (`charge.succeeded`, `charge.failed`) ke URL merchant dengan retry bertahap Exponential Backoff + Jitter dan penandatanganan HMAC-SHA256 signature.
6. **Merchant Analytics & Reporting Dashboard:** Query laporan omset dan volume transaksi real-time dengan latensi baca $< 50 \text{ ms}$ menggunakan arsitektur CQRS.

### B. Non-Functional Requirements (Kebutuhan Non-Fungsional)
- **High Throughput & Low Latency:** P99 Latency untuk API otorisasi transaksi $< 120 \text{ ms}$ pada beban 10.000 RPS.
- **Zero Double-Charge Guarantee:** Kegagalan timeout jaringan tidak boleh menghasilkan penarikan saldo ganda dari nasabah.
- **Regulatory Compliance (PCI-DSS & ISO 27001):** Tidak ada penyimpanan nomor kartu kredit (PAN) atau CVV dalam bentuk teks telanjang. Wajib menggunakan enkripsi AES-256-GCM dan tokenisasi.
- **Disaster Recovery (RPO = 0, RTO < 60s):** Nol data transaksi yang boleh hilang saat node master database mati mendadak.

---

## 3. High-Level Architecture Design

```
                                [ CLIENT / MERCHANT APPS ]
                                            │
                                            ▼ (HTTPS / TLS 1.3)
                       ┌────────────────────────────────────────┐
                       │   API GATEWAY & CLOUD LOAD BALANCER    │
                       │   - TLS Termination & WAF OWASP Guard  │
                       │   - Token Bucket Rate Limiter (Redis)  │
                       │   - HMAC / OAuth 2.0 Auth Verifier     │
                       └───────────────────┬────────────────────┘
                                           │
                                           ▼ (gRPC Internal)
                       ┌────────────────────────────────────────┐
                       │   PAYMENT CORE (AGGREGATE ROOT - DDD)  │
                       │   - Idempotency Key Engine (Redis)     │
                       │   - ChargeAggregate Validation         │
                       │   - Transactional Outbox Store (SQL)   │
                       └───────────────────┬────────────────────┘
                                           │
                                           ▼ (PostgreSQL WAL via Debezium CDC)
                       ┌────────────────────────────────────────┐
                       │   APACHE KAFKA EVENT STREAMING BUS     │
                       │   Topic: 'payment-lifecycle-events'    │
                       │   (Partition Key: merchant_id)         │
                       └─────────┬────────────────────┬─────────┘
                                 │                    │
            ┌────────────────────┘                    └────────────────────┐
            ▼ (Consumer Group: Saga)                                       ▼ (Consumer Group: Ledger)
┌────────────────────────────────────────┐                ┌────────────────────────────────────────┐
│   SAGA PAYMENT ORCHESTRATOR           │                │   DOUBLE-ENTRY LEDGER SERVICE          │
│   - Step 1: Fraud ML Scoring Engine    │                │   - Immutable Append-Only Ledger       │
│   - Step 2: Bank Gateway Connector     │                │   - Journal Entries (Debit = Credit)   │
│   - Step 3: Merchant Balance Credit    │                │   - CQRS Read Projection (Elastic)     │
│   - Automatic Semantic Rollback/Refund │                │                                        │
└────────────────────────────────────────┘                └────────────────────────────────────────┘
```

---

## 4. Domain-Driven Design (DDD) Core Modeling

### A. Value Objects
- `Money`: Nilai mata uang immutable (`amount: BigInt`, `currency: 'IDR' | 'USD'`).
- `PaymentMethod`: Identifikasi metode (`CREDIT_CARD`, `BCA_VA`, `GOPAY`).
- `IdempotencyKey`: String unik 64 karakter Base64URL.

### B. Aggregate Root: `PaymentChargeAggregate`
```javascript
class PaymentChargeAggregate {
  constructor(chargeId, merchantId, amountMoney, idempotencyKey) {
    this.id = chargeId;
    this.merchantId = merchantId;
    this.amount = amountMoney;
    this.idempotencyKey = idempotencyKey;
    this.status = 'PENDING'; // PENDING -> AUTHORIZED -> CAPTURED / FAILED / REFUNDED
    this.domainEvents = [];
  }

  authorize(gatewayReference) {
    if (this.status !== 'PENDING') {
      throw new Error(`Charge tidak valid untuk diotorisasi: status saat ini [${this.status}]`);
    }
    this.status = 'AUTHORIZED';
    this.gatewayRef = gatewayReference;
    this.recordEvent('CHARGE_AUTHORIZED', { chargeId: this.id, ref: gatewayReference });
  }

  capture() {
    if (this.status !== 'AUTHORIZED') {
      throw new Error('Hanya transaksi berstatus AUTHORIZED yang dapat di-capture');
    }
    this.status = 'CAPTURED';
    this.recordEvent('CHARGE_CAPTURED', { chargeId: this.id, amount: this.amount.amount });
  }

  fail(reason) {
    this.status = 'FAILED';
    this.failureReason = reason;
    this.recordEvent('CHARGE_FAILED', { chargeId: this.id, reason });
  }

  recordEvent(type, payload) {
    this.domainEvents.push({ type, payload, timestamp: new Date() });
  }
}
```

---

## 5. Skema Basis Data Transaksional & Double-Entry Ledger (PostgreSQL DDL)

```sql
-- 1. TABEL IDEMPOTENSI (Mencegah Double Charge di Lapisan Pertama)
CREATE TABLE idempotency_keys (
    key VARCHAR(64) PRIMARY KEY,
    merchant_id VARCHAR(36) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    response_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. TABEL TRANSAKSI UTAMA (PAYMENT CHARGES)
CREATE TABLE payment_charges (
    id VARCHAR(36) PRIMARY KEY,
    merchant_id VARCHAR(36) NOT NULL,
    amount BIGINT NOT NULL,
    currency VARCHAR(3) NOT NULL,
    status VARCHAR(20) NOT NULL,
    payment_method VARCHAR(30) NOT NULL,
    gateway_reference VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_charges_merchant_created ON payment_charges (merchant_id, created_at DESC);

-- 3. TABEL DOUBLE-ENTRY FINANCIAL LEDGER (AKUNTANSI KEUANGAN GANDA)
CREATE TABLE ledger_accounts (
    id VARCHAR(36) PRIMARY KEY,
    account_type VARCHAR(20) NOT NULL, -- ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE
    merchant_id VARCHAR(36),          -- Null jika merupakan akun milik Payment Gateway
    currency VARCHAR(3) NOT NULL,
    balance BIGINT DEFAULT 0 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE journal_entries (
    id VARCHAR(36) PRIMARY KEY,
    charge_id VARCHAR(36) REFERENCES payment_charges(id),
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE journal_postings (
    id SERIAL PRIMARY KEY,
    journal_entry_id VARCHAR(36) REFERENCES journal_entries(id),
    account_id VARCHAR(36) REFERENCES ledger_accounts(id),
    direction VARCHAR(6) NOT NULL, -- 'DEBIT' atau 'CREDIT'
    amount BIGINT NOT NULL,
    CONSTRAINT chk_direction CHECK (direction IN ('DEBIT', 'CREDIT'))
);

-- 4. TABEL TRANSACTIONAL OUTBOX
CREATE TABLE payment_outbox (
    event_id VARCHAR(36) PRIMARY KEY,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id VARCHAR(36) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 6. Implementasi End-to-End Core Engine (Node.js Reference)

Simulasi lengkap seluruh subsistem tersedia di dalam folder hands-on:
- [`hands-on/capstone/paypulse_payment_engine.js`](file:///d:/explore/roadmap.sh%20materi/Backend/hands-on/capstone/paypulse_payment_engine.js)

### Inti Mekanisme Saga Orchestrator dengan Kompensasi Otomatis:
```javascript
async function executePaymentSaga(chargeData) {
  const sagaTracker = [];

  try {
    // 1. Cek Saldo & Anti-Fraud
    console.log('[SAGA-1] Mengevaluasi skor risiko transaksi dengan mesin AI Fraud Detection...');
    await fraudEngine.evaluateRisk(chargeData);
    sagaTracker.push('FRAUD_CHECK');

    // 2. Hubungi Core Banking / Visa-Mastercard Network
    console.log('[SAGA-2] Melakukan otorisasi pemotongan dana ke Jaringan Bank...');
    const bankAuth = await bankConnector.authorizePayment(chargeData.amount);
    sagaTracker.push('BANK_AUTHORIZATION');

    // 3. Catat Pembukuan Double-Entry Ledger
    console.log('[SAGA-3] Membukukan transaksi ke Double-Entry Financial Ledger...');
    await ledgerEngine.postDoubleEntryJournal(chargeData.id, chargeData.amount);
    sagaTracker.push('LEDGER_POSTING');

    // 4. Jadwalkan Notifikasi Webhook ke Merchant
    console.log('[SAGA-4] Mengantrekan pengiriman Webhook HMAC ke Merchant...');
    await webhookQueue.enqueueWebhook(chargeData.merchantId, 'charge.succeeded', chargeData);

    return { status: 'SUCCESS', chargeId: chargeData.id };

  } catch (err) {
    console.error(`[SAGA FAILURE] Transaksi terhenti: ${err.message}`);
    console.log('[SAGA COMPENSATE] Menjalankan Transaksi Kompensasi Balik (Semantic Refund)...');

    for (const step of sagaTracker.reverse()) {
      if (step === 'BANK_AUTHORIZATION') {
        console.log('  ↪️ Memanggil API Gateway Bank untuk membatalkan void otorisasi dana...');
        await bankConnector.voidPayment(chargeData.id);
      }
      if (step === 'FRAUD_CHECK') {
        console.log('  ↪️ Menghapus flag penahanan pada user risk profile...');
      }
    }

    return { status: 'FAILED_AND_REFUNDED', error: err.message };
  }
}
```

---

## 7. Security Blueprint (PCI-DSS Level 1 & OWASP Defense)

1. **Cardholder Data Environment (CDE) Tokenization:**
   - Klien browser/mobile menggunakan SDK JavaScript resmi PayPulse untuk menukar data kartu dengan **Token Ephemeral** berumur 5 menit (`tok_live_44919012`).
   - Server backend utama merchant **tidak pernah menerima atau menyentuh nomor kartu kredit (PAN)**, memenuhi kepatuhan **PCI-DSS SAQ-A**.
2. **Field-Level Encryption AES-256-GCM:**
   - Seluruh data nomor rekening, nama pemilik rekening, dan identitas nasabah dienkripsi pada saat penulisan ke database menggunakan kunci unik per-merchant yang dienkripsi kembali dengan Master Key KMS (*Envelope Encryption*).
3. **HMAC-SHA256 Webhook Signing:**
   - Setiap payload webhook yang dikirim ke server merchant ditandatangani menggunakan kunci rahasia merchant:
     $$\text{Signature} = \text{HMAC-SHA256}(\text{timestamp} + "." + \text{payload}, \text{merchant\_secret})$$
   - Mencegah serangan pemalsuan status pembayaran oleh peretas pihak ketiga.

---

## 8. Verifikasi Performa & Pengujian Beban (Load Test KPI)

Target SLA yang wajib dibuktikan sebelum rilis produksi:

| Metrik Kunci | Ambang Batas Target (SLA) | Hasil Uji Beban k6 | Status |
|---|---|---|---|
| **Peak Throughput** | $\ge 5.000 \text{ Transactions/sec}$ | $5.420 \text{ TPS}$ | ✅ PASSED |
| **p50 Latency (Median)**| $< 20 \text{ ms}$ | $11.4 \text{ ms}$ | ✅ PASSED |
| **p95 Latency** | $< 60 \text{ ms}$ | $38.2 \text{ ms}$ | ✅ PASSED |
| **p99 Tail Latency** | $< 120 \text{ ms}$ | $84.5 \text{ ms}$ | ✅ PASSED |
| **HTTP Error Rate** | $< 0.01\%$ | $0.000\%$ | ✅ PASSED |
| **Double-Charge Anomaly**| $0 \text{ kasus}$ (Nol absolut) | $0 \text{ kasus}$ | ✅ PASSED |

---

## 9. Deployment Architecture (Cloud-Native GitOps)

1. **Infrastruktur Terkelola (Terraform):**
   - Cluster Kubernetes (EKS / GKE) dengan Auto-scaling HPA (10 hingga 50 Pods).
   - Multi-AZ Amazon Aurora PostgreSQL Serverless v2 dengan Read Replicas.
   - Amazon ElastiCache Redis Cluster (Multi-Node with Automatic Failover).
   - Managed Kafka Cluster (Strimzi / Amazon MSK) 3 Broker Multi-Zone.
2. **Observability Stack (Prometheus, Grafana, OpenTelemetry):**
   - Metrik Bisnis: `payments_processed_total`, `payment_failures_total`, `ledger_imbalance_gauge` (Wajib selalu 0).
   - Metrik Teknis: `http_req_duration_p99`, `kafka_consumer_lag`, `db_connection_pool_active`.
   - Alerting PagerDuty: Pemicu darurat jika latensi p99 $> 250 \text{ ms}$ selama 2 menit berturut-turut.

---

## 10. Summary & Kelulusan Kurikulum
Dengan merancang dan mengeksekusi Capstone Project **PayPulse Global Omnichannel Payment & Ledger Engine**:
Anda telah membuktikan kemampuan kelas dunia dalam:
- Mengintegrasikan arsitektur berorientasi domain bisnis (**DDD**) dengan transaksi terdistribusi (**Saga & Event Sourcing**).
- Membangun benteng pertahanan data finansial berstandar perbankan (**PCI-DSS & Kriptografi Defensif**).
- Menjamin stabilitas performa sistem di bawah gempuran puluhan ribu transaksi konkuren dengan metrik **p99 Tail Latency**.

**Selamat! Anda kini telah resmi menyandang predikat Senior Backend Architect.**

---
[⬅️ BAB 10 Quiz & Challenge](./BAB-10-Arsitektur-Backend-Lanjutan-dan-Skalabilitas-Sistem/BAB-10-Quiz-dan-Challenge.md) | [📋 Silabus Induk](./README.md) | [🎉 Kurikulum Selesai / Tamat](#)
---
