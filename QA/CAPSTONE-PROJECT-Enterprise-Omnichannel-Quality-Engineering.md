---
[⬅️ BAB 10: Quiz & Challenge](./BAB-10-CICD-Integration-Flaky-Test-dan-Quality-Gates/BAB-10-Quiz-dan-Challenge.md) | [📋 Silabus Induk](./README.md)
---

# 🏆 CAPSTONE PROJECT: Enterprise Omnichannel Quality Engineering Framework

## 1. Project Overview & Business Case
Selamat datang di proyek puncak **Capstone Project: QA Engineer Mastery**. Pada proyek ini, Anda akan berperan sebagai **Lead Quality Assurance Engineer / Principal SDET** untuk platform perbankan digital dan e-commerce omnichannel berskala enterprise bernama **"OmniNusantara Digital Ecosystem"**.

Aplikasi ini melayani jutaan transaksi harian melalui antarmuka Web Responsive, Mobile Apps (Android/iOS), dan Microservices REST API yang terintegrasi dengan Payment Gateway eksternal dan Core Banking Database.

Tujuan utama proyek capstone ini adalah merancang, mengimplementasikan, dan mengeksekusi **Sistem Rekayasa Kualitas Terpadu (Unified Quality Engineering System)** yang menggabungkan seluruh konsep dari BAB 01 hingga BAB 10 ke dalam satu ekosistem otomasi yang kohesif, deterministik, dan siap produksi (*Production-Ready*).

---

## 2. Arsitektur Solusi & Komponen yang Diintegrasikan

```text
========================================================================================
             OMNINUSANTARA UNIFIED QUALITY ENGINEERING ARCHITECTURE
========================================================================================

                 [ BUSINESS STAKEHOLDERS & PRODUCT SPECIFICATION ]
                                         |
                                         v
               [ BDD LIVING DOCUMENTATION: Gherkin Feature Files ]
                                         |
         +-------------------------------+-------------------------------+
         |                               |                               |
         v                               v                               v
 [ API CONTRACT LAYER ]        [ WEB UI AUTOMATION ]          [ MOBILE & ACCESSIBILITY ]
 - HTTP Status Semantics       - Playwright Headless Engine   - Appium W3C Touch Gestures
 - JSON Schema Validation      - Resilient User Locators      - axe-core WCAG 2.1 AA Audit
 - BOLA Security Penetration   - Storage State Auth Bypass    - Touch Target 48dp Checks
         |                               |                               |
         +-------------------------------+-------------------------------+
                                         |
                                         v
                         [ DATABASE & INTEGRITY LAYER ]
                         - ACID Atomicity Verification
                         - Foreign Key Cascade/Restrict Checks
                         - UU PDP / GDPR Synthetic Data Masking
                                         |
                                         v
                         [ PERFORMANCE & CAPACITY LAYER ]
                         - Grafana k6 Load & Spike Engine
                         - Latency Percentiles (p50, p95, p99)
                         - Little's Law Concurrency Modeling
                                         |
                                         v
                         [ CI/CD ORCHESTRATION & GATES ]
                         - GitHub Actions Parallel Sharding
                         - Flaky Test Quarantine Pattern
                         - Executive Allure Summary & Go/No-Go Decision
```

---

## 3. Milestone 1: Requirements & Risk-Based Testing Matrix

### Spesifikasi Alur Transaksi Kritis: "OmniPay Express Checkout"
1. Pengguna terotentikasi membuka keranjang belanja.
2. Menerapkan kode kupon diskon promo.
3. Memilih metode pembayaran dompet digital (OmniWallet) atau Virtual Account.
4. Sistem memverifikasi saldo, memotong kuota promo, mencatat transaksi ACID ke basis data, dan menerbitkan faktur digital (*Invoice*).

### Matriks Risiko & Alokasi Pengujian (Risk-Based Testing):

| Modul Fitur | Tingkat Risiko | Tingkatan Pengujian | Strategi Otomasi |
|---|---|---|---|
| **Otentikasi & Sesi** | R1 - Kritis | API & Web UI | Injeksi StorageState + JWT Token Validation. |
| **Kalkulasi Diskon & Pajak** | R1 - Kritis | Unit & Integration | Boundary Value Analysis (BVA) + Decision Table. |
| **Pencegahan BOLA / IDOR** | R1 - Kritis | Security API | Penetrasi manipulasi Resource ID antar-akun. |
| **Pembayaran & Mutasi Saldo**| R1 - Kritis | Database & ACID | Failure Injection Rollback + Idempotency-Key. |
| **Aksesibilitas Antarmuka**| R2 - Tinggi | Web & Mobile | axe-core WCAG 2.1 AA Scan (Zero Critical Issues). |
| **Ketahanan Lonjakan Traffic**| R2 - Tinggi | Performance k6 | Spike Test 0 $\to$ 2.000 VU dengan Threshold p95 $\le$ 300 ms. |

---

## 4. Milestone 2: Perancangan BDD Living Documentation

File: `specs/features/omnichannel_checkout.feature`

```gherkin
@regression @checkout @capstone
Feature: Transaksi Belanja Omnichannel Terintegrasi
  Sebagai nasabah terverifikasi OmniNusantara
  Saya ingin melakukan pembayaran belanja menggunakan saldo dompet digital
  Agar transaksi dapat selesai secara instan dan aman

  Background:
    Given nasabah telah terotentikasi dengan akun "nasabah.vip@omni.id"
    And saldo awal dompet nasabah adalah Rp 1.000.000

  Scenario: Pembayaran berhasil dengan diskon promo dan saldo mencukupi
    Given keranjang belanja berisi item senilai Rp 300.000
    When nasabah menerapkan voucher diskon "DISKON10"
    And nasabah mengonfirmasi pembayaran dengan PIN yang benar
    Then saldo akhir dompet nasabah terpotong menjadi Rp 730.000
    And sistem mencatat transaksi berstatus "COMPLETED" di database
    And faktur pembayaran digital terbit dengan kode unik berawalan "INV-"
```

---

## 5. Milestone 3: Lapisan Integritas Data & Kepatuhan Privasi (UU PDP)

1. **ACID Transaction Rule**:
   - Pemotongan saldo dompet nasabah dan pencatatan riwayat faktur wajib berada dalam 1 blok transaksi SQL. Jika terjadi kegagalan jaringan saat mencatat faktur, saldo nasabah wajib kembali utuh melalui operasi `ROLLBACK`.
2. **Kepatuhan Privasi Data Pribadi**:
   - Seluruh data nama, NIK, nomor telepon, dan email nasabah pada dataset staging wajib disamarkan menggunakan algoritma *Format Preserving Masking* (contoh: NIK `3171********0001` dan HP `0812****9988`).

---

## 6. Milestone 4: Lapisan Keamanan & Validasi Kontrak API

1. **JSON Schema Verification**:
   - Respon endpoint `POST /api/v1/checkout` wajib mematuhi skema deklaratif: `transactionId` (string format uuid), `totalPaid` (integer $> 0$), `status` (enum: SETTLED/PENDING/FAILED), dan `additionalProperties: false`.
2. **BOLA / IDOR Defense**:
   - Nasabah A dilarang membaca data faktur transaksi milik Nasabah B (`GET /api/v1/invoices/{invoiceId}`); server wajib merespon **HTTP 403 Forbidden**.
3. **Idempotency Defense**:
   - Header `Idempotency-Key` wajib disertakan. Pengulangan request yang sama tidak boleh memotong saldo dua kali.

---

## 7. Milestone 5: Lapisan Aksesibilitas & Uji Beban Performa

1. **Audit axe-core (WCAG 2.1 AA)**:
   - Halaman modal checkout wajib memiliki rasio kontras warna minimal 4.5:1 dan ukuran target sentuh tombol minimal $48 \times 48 \text{ dp}$.
2. **k6 Spike & Latency Thresholds**:
   - Menguji lonjakan traffic 1.000 Virtual Users secara bersamaan.
   - Ambang batas mutlak: $p95 \text{ latency} \le 300 \text{ ms}$ dan error rate $< 1\%$.

---

## 8. Milestone 6: Gerbang Kualitas Rilis Terpadu (The Master Quality Gate)

Kriteria Keputusan **GO / NO-GO** Peluncuran Produksi:
- [x] **0 Defek Kritis Aktif (Zero S1/S2 Bugs)**.
- [x] **100% Smoke Test Suite Lulus**.
- [x] **Flaky Test Rate $\le 2.0\%$** (Seluruh tes tidak stabil wajib dikarantina).
- [x] **Performance p95 Latency $\le 300 \text{ ms}$**.
- [x] **0 Pelanggaran Kritis Aksesibilitas (axe-core WCAG 2.1 AA)**.
- [x] **0 Kebocoran Data PII pada Database Staging**.

---

## 9. Hands-on Capstone: Unified Automation Engine Simulator

Jalankan skrip orkestrasi pengujian capstone terpadu yang mengeksekusi seluruh lapisan pengujian di atas dari hulu ke hilir secara otomatis:

```bash
node QA/hands-on/capstone/qa_omnichannel_automation_engine.js
```

---
[⬅️ BAB 10: Quiz & Challenge](./BAB-10-CICD-Integration-Flaky-Test-dan-Quality-Gates/BAB-10-Quiz-dan-Challenge.md) | [📋 Silabus Induk](./README.md)
---
