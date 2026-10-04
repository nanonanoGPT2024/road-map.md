---
[⬅️ BAB 10 Quiz & Challenge](./BAB-10-Serverless-Edge-Infrastructure-dan-Monorepo/BAB-10-Quiz-dan-Challenge.md) | [📋 Silabus Induk](./README.md)
---

# 🏆 CAPSTONE PROJECT: Enterprise Collaborative Workspace & SaaS Platform

## 1. Project Overview & Objective
Selamat datang di **Capstone Project: Full-Stack Developer Mastery**! Proyek puncak ini dirancang untuk mengintegrasikan seluruh konsep, teknik arsitektur, dan standar keamanan yang telah Anda pelajari dari Bab 01 hingga Bab 10 ke dalam satu platform perangkat lunak kelas dunia (*Enterprise-Grade SaaS*).

Anda akan merancang, mengimplementasikan, dan mengamankan **SyncSpace**: sebuah platform ruang kerja kolaboratif real-time terpadu (menggabungkan kapabilitas *Figma collaborative canvas*, *Notion document blocks*, dan *Stripe B2B subscription billing*).

```text
LEARN  ───>  UNDERSTAND  ───>  PRACTICE  ───>  BUILD  ───>  DEBUG  ───>  APPLY  ───>  MASTER
```

---

## 2. Business Domain & System Requirements

### A. Fitur Fungsional Utama (Core Features)
1. **Multi-Tenant Collaborative Canvas & Document**:
   - Kanvas kolaboratif di mana ratusan pengguna dalam satu organisasi dapat menggambar, memindahkan komponen, dan mengetik teks secara real-time.
   - Sinkronisasi kursor pengguna (*User Live Cursor Tracking*) berlatensi rendah dengan payload biner terkompresi.
   - Resolusi konflik pengeditan bersama (*Conflict Resolution*) menggunakan algoritma **CRDT (Conflict-free Replicated Data Types)**.
2. **Passwordless Biometric Authentication (Passkeys / WebAuthn)**:
   - Pengguna login dalam 1 klik menggunakan sensor biometrik (Apple Touch ID / Face ID / Windows Hello) dengan perlindungan kebal phishing (*Origin-bound RP ID*).
   - Dukungan fallback menggunakan TOTP Authenticator (RFC 6238) dan Magic Links.
3. **End-to-End Type-Safe Data Operations**:
   - Komunikasi frontend-backend tanpa API generator via **tRPC** dan **Zod runtime schema parsing**.
4. **Resilient Data Layer**:
   - Skema database relasional **PostgreSQL** yang dimodelkan via **Drizzle ORM** dengan perlindungan **PgBouncer Transaction Pooling** dan **Upstash Redis Edge Caching**.
5. **B2B Stripe Subscription & Webhooks**:
   - Manajemen paket berlangganan (`STARTER`, `PROFESSIONAL`, `ENTERPRISE`) dengan kuota kursi tim (*Seat-based billing*).
   - Pemrosesan event webhook Stripe yang aman dan *idempotent*.
6. **Progressive Web App (PWA) Offline-First**:
   - Pengguna tetap dapat membaca dan menyusun draft dokumen saat koneksi internet mati via **IndexedDB Outbox** dan tersinkronisasi otomatis via **Background Sync**.

### B. Persyaratan Non-Fungsional (Non-Functional Requirements)
- **Ketersediaan (SLA)**: 99.99% dengan arsitektur failover multi-region di Edge CDN.
- **Performa Core Web Vitals**: P75 LCP < 1.8 detik, INP < 150 milidetik, CLS < 0.05.
- **Keamanan Defensif**: Kepatuhan penuh terhadap OWASP Web & API Top 10 (Dynamic CSP Nonces, SSRF IP Blocklist, proteksi CSRF pada Server Actions, dan HTTP Security Headers).
- **Observabilitas Penuh**: Pelacakan jejak terdistribusi W3C `traceparent` dari klik browser hingga baris query SQL PostgreSQL via **OpenTelemetry**.

---

## 3. High-Level Architecture Diagram

```
+-----------------------------------------------------------------------------------+
| CLIENT LAYER (Progressive Web App - Browser & Mobile)                            |
|                                                                                   |
|  [ Next.js 14 App Router (RSC + Client Components) ]                              |
|  [ Real User Monitoring (Core Web Vitals Collector) ]                             |
|  [ Service Worker Proxy (Cache API + IndexedDB Offline Outbox) ]                  |
|  [ WebAuthn Browser API (Biometric TouchID / FaceID) ]                            |
+-----------------------------------------------------------------------------------+
                                        |
     (W3C traceparent + __Host- JWT Cookie + Dynamic CSP Nonce)
                                        v
+-----------------------------------------------------------------------------------+
| EDGE INFRASTRUCTURE LAYER (Cloudflare / Vercel Edge Global PoP)                   |
|                                                                                   |
|  - Edge Middleware: Cryptographic Token Verification (< 1ms)                      |
|  - Dynamic CSP Nonce Injection & Security Headers                                 |
|  - Geo-IP Routing & Localization (Mata uang, bahasa, estimasi latensi)            |
|  - Edge Caching Gateway (Upstash Redis REST API sub-5ms)                          |
+-----------------------------------------------------------------------------------+
                                        |
                +-----------------------+-----------------------+
                | (HTTP / RPC)                                  | (WebSocket wss://)
                v                                               v
+------------------------------------+        +-------------------------------------+
| SERVERLESS COMPUTE (Next.js Node)  |        | STATEFUL REAL-TIME CLUSTER (Node/WS)|
|                                    |        |                                     |
|  - tRPC Router & Zod Validation    |        |  - Collaborative Document Canvas    |
|  - React Server Actions            |        |  - Live Cursor Presence Engine      |
|  - SSRF-Safe Webhook Dispatcher    |        |  - Ping/Pong Heartbeat Monitor      |
|  - Stripe Webhook Idempotency      |        |  - CRDT State Reconciliation        |
+------------------------------------+        +-------------------------------------+
                |                                               |
                | (Pooled SQL TCP 6543)                         | (Pub/Sub Broadcast)
                v                                               v
+------------------------------------+        +-------------------------------------+
| CONNECTION POOLER (PgBouncer)      |        | REDIS DISTRIBUTED MESSAGE BROKER    |
|                                    |        |                                     |
| Multiplexing ribuan request ke DB  |        | - Multi-Node Sync Channel           |
+------------------------------------+        | - User Online Presence Key (TTL 45s)|
                |                             +-------------------------------------+
                v
+-----------------------------------------------------------------------------------+
| PERSISTENT DATABASE LAYER (Serverless PostgreSQL / Neon Branching)                |
|                                                                                   |
|  - Drizzle ORM Type-Safe Schemas (Users, Workspaces, Documents, Subscriptions)    |
|  - Multi-Region Read Replicas dengan Session Pinning ("Read-Your-Own-Writes")     |
+-----------------------------------------------------------------------------------+
```

---

## 4. Multi-Milestone Implementation Plan

### Milestone 1: Fondasi Monorepo & End-to-End Type Safety
- **Tujuan**: Membangun workspace Turborepo terpadu dengan pnpm workspaces.
- **Deliverables**:
  - `apps/web`: Next.js 14 App Router.
  - `packages/database`: Skema Drizzle ORM.
  - `packages/trpc`: Definisi router API dan skema Zod terpusat.
  - `turbo.json`: Konfigurasi dependensi tugas dan pipeline build topologis.

### Milestone 2: Data Layer Relasional & Connection Pooling
- **Tujuan**: Merancang skema database yang efisien dan kebal dari *connection exhaustion*.
- **Deliverables**:
  - Tabel: `users`, `workspaces`, `workspace_members`, `documents`, `audit_logs`, `subscriptions`.
  - Integrasi driver PostgreSQL dengan connection pooler PgBouncer port 6543.
  - Implementasi fungsi transaksi atomik dengan *Row-Level Locking* (`SELECT ... FOR UPDATE`) untuk mencegah race condition.

### Milestone 3: Autentikasi Biometrik & Edge Session Guards
- **Tujuan**: Menerapkan sistem login tanpa kata sandi yang kebal phishing.
- **Deliverables**:
  - Seremoni registrasi dan otentikasi Passkeys (WebAuthn / FIDO2) menggunakan modul kriptografi ECDSA P-256.
  - Verifikasi signature cookie `__Host-authjs.session-token` di Edge Middleware tanpa memanggil database pusat.
  - Role-Based Access Control (RBAC): `OWNER`, `EDITOR`, `VIEWER`.

### Milestone 4: Real-Time Collaborative Canvas (CRDT & Redis Pub/Sub)
- **Tujuan**: Membangun kanvas kolaboratif multi-node yang dapat diskalakan secara horizontal.
- **Deliverables**:
  - Server WebSocket mandiri dengan integrasi Redis Pub/Sub channel adapter.
  - Protokol Heartbeat (Ping/Pong) untuk membersihkan *Zombie Sockets*.
  - Mekanisme rekoneksi client menggunakan *Exponential Backoff dengan Random Jitter*.
  - Resolusi konflik dokumen menggunakan prinsip CRDT.

### Milestone 5: Keamanan Defensif Berlapis (OWASP Web & API Top 10)
- **Tujuan**: Mengunci seluruh potensi celah keamanan di frontend dan backend.
- **Deliverables**:
  - Dynamic CSP Nonces yang diterbitkan per request oleh Edge Middleware.
  - Anti-Clickjacking via `frame-ancestors 'none'`.
  - SSRF IP & DNS Resolver Shield untuk mencegah akses ke IP privat RFC 1918 dan metadata cloud (`169.254.169.254`).
  - Sanitasi parameter Server Action untuk mencegah *Mass Assignment*.

### Milestone 6: B2B Stripe Billing & Idempotent Webhook Engine
- **Tujuan**: Mengotomatisasi monetisasi platform SaaS dengan penagihan berbasis kursi (*seats*).
- **Deliverables**:
  - Alur checkout langganan Stripe.
  - Webhook listener dengan verifikasi cryptographic signature Stripe.
  - Tabel `processed_webhooks` untuk menjamin bahwa event webhook yang terkirim ganda tidak akan diproses dua kali (*Idempotency Key Guard*).

### Milestone 7: Pengujian Otomatis (Playwright) & Observabilitas (OpenTelemetry)
- **Tujuan**: Menjamin kualitas software secara berkelanjutan dan visibilitas performa end-to-end.
- **Deliverables**:
  - Skenario pengujian E2E Playwright: login, buat workspace, undang anggota, dan checkout langganan dengan network mocking.
  - Pengujian visual regression layout antarmuka.
  - OpenTelemetry SDK dengan propagasi W3C `traceparent` dan pelacakan metrik Core Web Vitals (P75 LCP, INP, CLS).

### Milestone 8: Multi-Stage Docker Standalone & GitOps CI/CD
- **Tujuan**: Mengemas aplikasi menjadi artefak produksi yang aman, ringan, dan siap di-deploy secara otomatis.
- **Deliverables**:
  - Dockerfile multi-stage dengan Next.js `output: "standalone"` (< 100MB).
  - Eksekusi container dengan user non-root `nextjs:nodejs` (UID 1001).
  - Pipeline GitHub Actions CI/CD dengan Turborepo Remote Caching.

---

## 5. Capstone Simulation Engine
Sebagai bagian integral dari Capstone Project ini, kami telah menyusun **Collaborative SaaS Engine Simulator** yang menggabungkan seluruh komponen di atas menjadi satu skrip mandiri yang dapat langsung dijalankan dan diuji di workspace Anda:

```bash
node Full-Stack/hands-on/capstone/collaborative_saas_engine.js
```

---

## 6. Verification & Acceptance Criteria
Sebuah implementasi dinyatakan **Lulus dengan Predikat Master (Certified Full-Stack Engineer)** jika memenuhi kriteria berikut:

| Area Evaluasi | Kriteria Kelulusan Mutlak |
| :--- | :--- |
| **Type Safety** | 100% Type-Safe dari database (Drizzle) ke tRPC router hingga ke komponen React client tanpa `any`. |
| **Keamanan** | Lolos audit SSRF (IP privat ditolak), CSP Nonce aktif di semua inline script, dan CSRF dicegat. |
| **Skalabilitas** | Seluruh query database melalui connection pooler (tidak ada koneksi bocor saat lonjakan 50 request). |
| **Real-Time** | Pesan kolaborasi disebarkan ke seluruh node server via Redis Pub/Sub tanpa membebani event loop. |
| **Container** | Image Docker Next.js Standalone berbobot di bawah 120MB dan berjalan sebagai user unprivileged. |
| **Core Web Vitals** | P75 LCP $\le 2.5$ detik, INP $\le 200$ ms, dan CLS $\le 0.1$. |

---
[⬅️ BAB 10 Quiz & Challenge](./BAB-10-Serverless-Edge-Infrastructure-dan-Monorepo/BAB-10-Quiz-dan-Challenge.md) | [📋 Silabus Induk](./README.md)
---
