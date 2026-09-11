# ⚡ Kurikulum Lengkap: Full-Stack Developer Mastery

> **Tujuan Kurikulum**: Mentransformasi pengembang perangkat lunak menjadi **Principal Full-Stack Engineer / Full-Stack System Architect** yang menguasai ekosistem web modern end-to-end: arsitektur render browser (SSR/CSR/RSC), framework generasi baru (Next.js App Router), end-to-end type safety (TypeScript & tRPC), lapisan data (ORMs & Edge DBs), real-time WebSockets, keamanan web defensif (OWASP Web & API), pengujian E2E (Playwright), observabilitas RUM, hingga orkestrasi infrastruktur serverless di Edge Cloud.

---

## 🗺️ Peta Jalan Pembelajaran (Learning Roadmap)

```
[ ARSITEKTUR FULL-STACK & BROWSER INTERNALS ] ──> [ MODERN FRONTEND: REACT FIBER & STATE ]
                                                                     │
                                                                     v
[ END-TO-END TYPE SAFETY (TS & tRPC) ] <── [ META-FRAMEWORKS: NEXT.JS RSC & STREAMING ]
       │
       v
[ DATA LAYER: ORMS, SERVERLESS DB, & CACHE ] ──> [ AUTHENTICATION & PASSKEYS (WEBAUTHN) ]
                                                                     │
                                                                     v
[ SECURITY DEFENSIF (XSS, CSP, CSRF, SSRF) ] <── [ REAL-TIME WEBSOCKETS & PWA OFFLINE ]
       │
       v
[ TESTING E2E (PLAYWRIGHT) & OBSERVABILITAS ] ──> [ SERVERLESS, EDGE DEPLOYMENT, & MONOREPO ]
                                                                     │
                                                                     v
[ 🏆 CAPSTONE PROJECT: ENTERPRISE COLLABORATIVE SAAS WORKSPACE & MARKETPLACE ]
```

---

## 📚 Daftar Bab & Modul Pembelajaran

### [BAB 01: Arsitektur Full-Stack Modern, Web Standards, & DOM/CSS Internals](./BAB-01-Arsitektur-Full-Stack-dan-Browser-Internals/)
- [Module 01: Paradigma Render Web: SSR, CSR, SSG, ISR, Hydration, & Core Web Vitals](./BAB-01-Arsitektur-Full-Stack-dan-Browser-Internals/Module-01-Paradigma-Render-SSR-CSR-SSG-ISR-Hydration.md)
- [Module 02: Browser Critical Rendering Path: DOM, CSSOM, Layout/Reflow, Repaint, & GPU Compositing](./BAB-01-Arsitektur-Full-Stack-dan-Browser-Internals/Module-02-Browser-Rendering-Pipeline-DOM-Layout-Composite.md)
- [Praktikum Hands-on: Simulator SSR vs CSR Hydration & Time-to-Interactive](./BAB-01-Arsitektur-Full-Stack-dan-Browser-Internals/hands-on/m01/ssr_csr_hydration_sim.js)
- [Praktikum Hands-on: Simulator Browser Critical Rendering Path & Reflow Detection](./BAB-01-Arsitektur-Full-Stack-dan-Browser-Internals/hands-on/m02/browser_critical_rendering_path_sim.js)
- [BAB 01 Quiz & Chapter Challenge](./BAB-01-Arsitektur-Full-Stack-dan-Browser-Internals/BAB-01-Quiz-dan-Challenge.md)

### [BAB 02: Modern Frontend Engineering: React Internals, Virtual DOM, & State Management](./BAB-02-React-Internals-dan-State-Management/)
- [Module 01: React Fiber Reconciler, Heuristic Diffing O(N), Hooks Mechanics, & Concurrent Mode](./BAB-02-React-Internals-dan-State-Management/Module-01-React-Fiber-Reconciler-Diffing-dan-Concurrent.md)
- [Module 02: State Management: Server State (TanStack Query) vs Client State (Zustand) & Optimistic UI](./BAB-02-React-Internals-dan-State-Management/Module-02-Server-State-Client-State-dan-Optimistic-UI.md)
- [Praktikum Hands-on: Simulator React Fiber WorkLoop & Virtual DOM Diffing Engine](./BAB-02-React-Internals-dan-State-Management/hands-on/m01/react_fiber_reconciler_sim.js)
- [Praktikum Hands-on: Simulator Optimistic UI Updates & Automatic Network Rollback](./BAB-02-React-Internals-dan-State-Management/hands-on/m02/optimistic_ui_state_sync_sim.js)
- [BAB 02 Quiz & Chapter Challenge](./BAB-02-React-Internals-dan-State-Management/BAB-02-Quiz-dan-Challenge.md)

### [BAB 03: Full-Stack Frameworks & Meta-Frameworks (Next.js App Router)](./BAB-03-Meta-Frameworks-Nextjs-App-Router/)
- [Module 01: React Server Components (RSC) vs Client Components, Streaming SSR, & Server Actions](./BAB-03-Meta-Frameworks-Nextjs-App-Router/Module-01-React-Server-Components-Streaming-SSR-Server-Actions.md)
- [Module 02: Next.js Multi-Layer Caching, Revalidation (On-demand/Time-based), & Edge Middleware Routing](./BAB-03-Meta-Frameworks-Nextjs-App-Router/Module-02-Nextjs-Multi-Layer-Caching-dan-Edge-Middleware.md)
- [Praktikum Hands-on: Simulator RSC Protocol Serialization & Streaming HTML SSR](./BAB-03-Meta-Frameworks-Nextjs-App-Router/hands-on/m01/rsc_streaming_ssr_sim.js)
- [Praktikum Hands-on: Simulator Next.js 4-Tier Caching Lifecycle & On-Demand Revalidation](./BAB-03-Meta-Frameworks-Nextjs-App-Router/hands-on/m02/nextjs_caching_lifecycle_sim.js)
- [BAB 03 Quiz & Chapter Challenge](./BAB-03-Meta-Frameworks-Nextjs-App-Router/BAB-03-Quiz-dan-Challenge.md)

### [BAB 04: End-to-End Type Safety: TypeScript Mastery & Schema Validation](./BAB-04-End-to-End-Type-Safety-TypeScript-tRPC/)
- [Module 01: Advanced TypeScript: Generics, Conditional Types, Template Literals, & Discriminated Unions](./BAB-04-End-to-End-Type-Safety-TypeScript-tRPC/Module-01-Advanced-TypeScript-Generics-Conditional-Types.md)
- [Module 02: Full-Stack Type Safety: tRPC (Zero-API Glue), Zod Parsing, & RPC Procedure Routers](./BAB-04-End-to-End-Type-Safety-TypeScript-tRPC/Module-02-tRPC-Zod-Validation-dan-Contract-First-APIs.md)
- [Praktikum Hands-on: Simulator TypeScript Type Inference Engine & Type Narrowing](./BAB-04-End-to-End-Type-Safety-TypeScript-tRPC/hands-on/m01/advanced_typescript_meta_types_sim.js)
- [Praktikum Hands-on: Simulator tRPC Router & Zod Input Validation Bridge](./BAB-04-End-to-End-Type-Safety-TypeScript-tRPC/hands-on/m02/trpc_zod_end_to_end_safety_sim.js)
- [BAB 04 Quiz & Chapter Challenge](./BAB-04-End-to-End-Type-Safety-TypeScript-tRPC/BAB-04-Quiz-dan-Challenge.md)

### [BAB 05: Full-Stack Data Layer: ORMs, Migrasi, & Caching Gateway](./BAB-05-Data-Layer-ORMs-dan-Serverless-Databases/)
- [Module 01: Modern ORMs & Query Builders: Prisma vs Drizzle vs Kysely, Connection Pooling, & Serverless Cold Starts](./BAB-05-Data-Layer-ORMs-dan-Serverless-Databases/Module-01-Modern-ORMs-Drizzle-Prisma-Connection-Pooling.md)
- [Module 02: Serverless Database Scaling: Neon / PlanetScale, Upstash Redis Edge Caching, & Zero-Downtime Migrations](./BAB-05-Data-Layer-ORMs-dan-Serverless-Databases/Module-02-Serverless-DB-Edge-Caching-Zero-Downtime-Migration.md)
- [Praktikum Hands-on: Simulator Drizzle Type-Safe SQL Query Builder & Connection Pool Pooler](./BAB-05-Data-Layer-ORMs-dan-Serverless-Databases/hands-on/m01/orm_query_builder_cold_start_sim.js)
- [Praktikum Hands-on: Simulator Edge Multi-Region Database Read Router & Cache Sync](./BAB-05-Data-Layer-ORMs-dan-Serverless-Databases/hands-on/m02/edge_db_replica_router_sim.js)
- [BAB 05 Quiz & Chapter Challenge](./BAB-05-Data-Layer-ORMs-dan-Serverless-Databases/BAB-05-Quiz-dan-Challenge.md)

### [BAB 06: Autentikasi & Sesi Full-Stack: Auth.js, Passkeys (WebAuthn), & MFA](./BAB-06-Autentikasi-Full-Stack-dan-WebAuthn/)
- [Module 01: Auth.js / NextAuth Architecture: Secure JWT Cookies, OAuth 2.0 PKCE, & Edge Middleware Route Guards](./BAB-06-Autentikasi-Full-Stack-dan-WebAuthn/Module-01-Authjs-Secure-Cookies-OAuth-Edge-Guards.md)
- [Module 02: Passwordless Security: WebAuthn / Passkeys (FIDO2 Biometrics), Magic Links, & TOTP Multi-Factor](./BAB-06-Autentikasi-Full-Stack-dan-WebAuthn/Module-02-Passwordless-WebAuthn-Passkeys-TOTP-MFA.md)
- [Praktikum Hands-on: Simulator NextAuth Edge Middleware Token Verification & RBAC Guard](./BAB-06-Autentikasi-Full-Stack-dan-WebAuthn/hands-on/m01/nextauth_edge_session_guard_sim.js)
- [Praktikum Hands-on: Simulator WebAuthn / Passkey Biometric Registration & Assertion](./BAB-06-Autentikasi-Full-Stack-dan-WebAuthn/hands-on/m02/webauthn_passkey_fido2_sim.js)
- [BAB 06 Quiz & Chapter Challenge](./BAB-06-Autentikasi-Full-Stack-dan-WebAuthn/BAB-06-Quiz-dan-Challenge.md)

### [BAB 07: Real-Time Systems, WebSockets, & PWA Offline-First](./BAB-07-Real-Time-WebSockets-dan-PWA-Offline/)
- [Module 01: Real-Time Architecture: WebSockets, Server-Sent Events (SSE), Pusher/Ably, & Scaling dengan Redis Pub/Sub](./BAB-07-Real-Time-WebSockets-dan-PWA-Offline/Module-01-WebSockets-SSE-dan-Redis-PubSub-Clustering.md)
- [Module 02: Progressive Web Apps (PWA): Service Workers, Cache API, Offline-First Sync, & Web Push Notifications](./BAB-07-Real-Time-WebSockets-dan-PWA-Offline/Module-02-PWA-Service-Workers-Offline-First-dan-Web-Push.md)
- [Praktikum Hands-on: Simulator Full-Stack WebSocket Chat Server dengan Redis Pub/Sub Adapter](./BAB-07-Real-Time-WebSockets-dan-PWA-Offline/hands-on/m01/fullstack_websocket_redis_pubsub_sim.js)
- [Praktikum Hands-on: Simulator Service Worker Offline Cache Engine & Background Sync Queue](./BAB-07-Real-Time-WebSockets-dan-PWA-Offline/hands-on/m02/service_worker_offline_sync_sim.js)
- [BAB 07 Quiz & Chapter Challenge](./BAB-07-Real-Time-WebSockets-dan-PWA-Offline/BAB-07-Quiz-dan-Challenge.md)

### [BAB 08: Keamanan Full-Stack Defensif (OWASP Web & API Top 10)](./BAB-08-Keamanan-Full-Stack-Defensif-OWASP/)
- [Module 01: Frontend Security: XSS Mitigation, Content Security Policy (CSP Nonces), CSRF, & Clickjacking Defense](./BAB-08-Keamanan-Full-Stack-Defensif-OWASP/Module-01-XSS-CSP-Nonces-CSRF-dan-Clickjacking-Defense.md)
- [Module 02: Backend & Supply Chain Defense: SSRF, Server Actions Parameter Tampering, & CORS Isolation](./BAB-08-Keamanan-Full-Stack-Defensif-OWASP/Module-02-SSRF-Server-Action-Tampering-dan-CORS-Isolation.md)
- [Praktikum Hands-on: Simulator Content Security Policy (CSP) Evaluator & XSS Interceptor](./BAB-08-Keamanan-Full-Stack-Defensif-OWASP/hands-on/m01/csp_nonce_xss_defense_sim.js)
- [Praktikum Hands-on: Simulator Server Action SSRF Validator & Input Sanitizer](./BAB-08-Keamanan-Full-Stack-Defensif-OWASP/hands-on/m02/server_action_ssrf_sanitizer_sim.js)
- [BAB 08 Quiz & Chapter Challenge](./BAB-08-Keamanan-Full-Stack-Defensif-OWASP/BAB-08-Quiz-dan-Challenge.md)

### [BAB 09: Pengujian Full-Stack (E2E), Observabilitas, & Web Vitals](./BAB-09-Testing-E2E-Playwright-dan-Observabilitas/)
- [Module 01: End-to-End Testing Modern: Playwright Automation, Component Testing, & Visual Regression](./BAB-09-Testing-E2E-Playwright-dan-Observabilitas/Module-01-Playwright-E2E-Automation-dan-Component-Testing.md)
- [Module 02: Full-Stack Observability: OpenTelemetry Tracing (Browser RUM to Database Spans) & Core Web Vitals](./BAB-09-Testing-E2E-Playwright-dan-Observabilitas/Module-02-OpenTelemetry-FullStack-Tracing-dan-Core-Web-Vitals.md)
- [Praktikum Hands-on: Simulator Playwright Headless Browser Test Runner & Network Mocks](./BAB-09-Testing-E2E-Playwright-dan-Observabilitas/hands-on/m01/e2e_browser_test_runner_sim.js)
- [Praktikum Hands-on: Simulator OpenTelemetry Distributed Context Propagation & Web Vitals Collector](./BAB-09-Testing-E2E-Playwright-dan-Observabilitas/hands-on/m02/opentelemetry_fullstack_tracing_sim.js)
- [BAB 09 Quiz & Chapter Challenge](./BAB-09-Testing-E2E-Playwright-dan-Observabilitas/BAB-09-Quiz-dan-Challenge.md)

### [BAB 10: Serverless, Edge Infrastructure, Monorepo, & CI/CD](./BAB-10-Serverless-Edge-Infrastructure-dan-Monorepo/)
- [Module 01: Serverless & Edge Computing: Vercel/Cloudflare Workers, Cold Starts Elimination, & Edge Rendering](./BAB-10-Serverless-Edge-Infrastructure-dan-Monorepo/Module-01-Serverless-Cloudflare-Edge-Workers-Cold-Starts.md)
- [Module 02: Full-Stack Monorepos (Turborepo), Dockerizing Next.js, & Multi-Stage Deployment GitOps](./BAB-10-Serverless-Edge-Infrastructure-dan-Monorepo/Module-02-Turborepo-Docker-Containerization-dan-GitOps.md)
- [Praktikum Hands-on: Simulator Serverless Cold Start vs Edge Compute Latency Benchmarker](./BAB-10-Serverless-Edge-Infrastructure-dan-Monorepo/hands-on/m01/serverless_edge_cold_start_sim.js)
- [Praktikum Hands-on: Simulator Turborepo Remote Caching & Monorepo Build Graph Dependency Resolver](./BAB-10-Serverless-Edge-Infrastructure-dan-Monorepo/hands-on/m02/turborepo_monorepo_pipeline_sim.js)
- [BAB 10 Quiz & Chapter Challenge](./BAB-10-Serverless-Edge-Infrastructure-dan-Monorepo/BAB-10-Quiz-dan-Challenge.md)

---

## 🏆 [CAPSTONE PROJECT: Enterprise Collaborative Workspace & Marketplace (SaaS)](./CAPSTONE-PROJECT-Enterprise-Collaborative-Workspace-SaaS.md)
Arsitektur dan implementasi platform SaaS kolaboratif real-time enterprise (seperti Figma + Notion + Stripe Subscription) yang mengintegrasikan Next.js 14 App Router, React Server Components, tRPC, Drizzle ORM dengan PostgreSQL, WebSockets kolaboratif (CRDT), Upstash Redis, Passkeys (WebAuthn), dan Stripe Billing.
