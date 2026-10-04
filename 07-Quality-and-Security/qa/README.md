# QA Engineer Mastery: From Manual Testing to Modern Test Automation & Quality Engineering

Selamat datang di kurikulum komprehensif **QA Engineer Mastery**, yang disusun secara mendalam dan sistematis mengacu pada standar kurikulum resmi [roadmap.sh/qa](https://roadmap.sh/qa) serta standar internasional industri perangkat lunak (ISTQB, W3C, ISO/IEC/IEEE 29119).

Kurikulum ini dirancang untuk mengubah pembelajar dari pemahaman dasar pengujian manual (*manual testing*) menuju kemampuan rekayasa kualitas modern (*Modern Quality Engineering & Software Development Engineer in Test / SDET*): mencakup perancangan test case matematis, otomasi Web UI & API, pengujian beban (performance load testing), hingga orkestrasi pipeline CI/CD dengan Quality Gates.

---

## 🎯 Prinsip Utama Pembelajaran
Materi ini mengikuti filosofi edukasi praktis:
```text
LEARN  ───>  UNDERSTAND  ───>  PRACTICE  ───>  BUILD  ───>  DEBUG  ───>  APPLY  ───>  MASTER
```
Setiap modul dirancang mandiri, mendalam, tanpa kompromi teknis, dan dilengkapi dengan **script laboratorium interaktif di folder `hands-on/` (zero external dependencies)** yang dapat langsung dieksekusi di Node.js.

---

## 🗺️ Learning Roadmap Overview

```text
[ TAHAP 1: FONDASI KUALITAS & STLC ]
  ├── BAB 01: Fondasi Software Testing, Kualitas Perangkat Lunak, & STLC
  └── BAB 02: Tingkatan & Tipe Pengujian (Functional vs Non-Functional)
         │
         v
[ TAHAP 2: TEST DESIGN & TEKNIK VERIFIKASI ]
  ├── BAB 03: Teknik Perancangan Test Case (Black-Box & White-Box)
  └── BAB 04: Pengujian API & Validasi Kontrak Data (REST, JSON Schema, Mocking)
         │
         v
[ TAHAP 3: REKAYASA OTOMASI PENGUJIAN (SDET CORE) ]
  ├── BAB 05: Fondasi Otomasi Pengujian & Pemrograman untuk QA (Node.js & POM)
  ├── BAB 06: Otomasi Pengujian Web UI Modern (Playwright & Cypress)
  └── BAB 07: Pengujian Database, Integritas Data, & Test Data Management (TDM)
         │
         v
[ TAHAP 4: ADVANCED TESTING & CONTINUOUS QUALITY ]
  ├── BAB 08: Pengujian Performa & Beban Sistem (k6, JMeter, Stress & Spike)
  ├── BAB 09: Pengujian Berbasis Perilaku (BDD Gherkin), Mobile, & Aksesibilitas (a11y)
  └── BAB 10: CI/CD Integration, Flaky Test Mitigation, & Quality Gates
         │
         v
[ 🏆 CAPSTONE PROJECT: ENTERPRISE OMNICHANNEL QUALITY ENGINEERING SUITE ]
```

---

## 📚 Daftar Bab & Modul Pembelajaran

### [BAB 01: Fondasi Software Testing, Kualitas Perangkat Lunak, & STLC](./BAB-01-Fondasi-Software-Testing-dan-STLC/)
- [Module 01: Prinsip Dasar Testing: Verification vs Validation, 7 Prinsip Testing (ISTQB), dan Kualitas Perangkat Lunak](./BAB-01-Fondasi-Software-Testing-dan-STLC/Module-01-Prinsip-Dasar-Testing-Verification-vs-Validation.md)
- [Module 02: Siklus Hidup Pengujian: SDLC vs STLC, Dokumen Uji (Test Plan, Test Strategy), dan Bug Lifecycle](./BAB-01-Fondasi-Software-Testing-dan-STLC/Module-02-SDLC-STLC-dan-Bug-Defect-Lifecycle.md)
- [Praktikum Hands-on: Simulator Assertion Engine & Regression Detector](./BAB-01-Fondasi-Software-Testing-dan-STLC/hands-on/m01/testing_fundamentals_assertions_sim.js)
- [Praktikum Hands-on: Simulator STLC State Machine & Defect Tracker](./BAB-01-Fondasi-Software-Testing-dan-STLC/hands-on/m02/stlc_bug_lifecycle_sim.js)
- [BAB 01 Quiz & Chapter Challenge](./BAB-01-Fondasi-Software-Testing-dan-STLC/BAB-01-Quiz-dan-Challenge.md)

### [BAB 02: Tingkatan & Tipe Pengujian (Functional vs Non-Functional)](./BAB-02-Tingkatan-dan-Tipe-Pengujian/)
- [Module 01: Pengujian Fungsional: Unit, Integration, System, UAT, Smoke, Sanity, & Regression Testing](./BAB-02-Tingkatan-dan-Tipe-Pengujian/Module-01-Pengujian-Fungsional-Unit-Integrasi-Sistem-Regression.md)
- [Module 02: Pengujian Non-Fungsional: Performance, Security, Usability, & Accessibility (WCAG / a11y)](./BAB-02-Tingkatan-dan-Tipe-Pengujian/Module-02-Pengujian-Non-Fungsional-Security-Usability-A11y.md)
- [Praktikum Hands-on: Simulator Testing Pyramid Runner & Regression Impact Analyzer](./BAB-02-Tingkatan-dan-Tipe-Pengujian/hands-on/m01/testing_pyramid_runner_sim.js)
- [Praktikum Hands-on: Simulator Accessibility WCAG DOM Auditor & Color Contrast Checker](./BAB-02-Tingkatan-dan-Tipe-Pengujian/hands-on/m02/a11y_wcag_dom_auditor_sim.js)
- [BAB 02 Quiz & Chapter Challenge](./BAB-02-Tingkatan-dan-Tipe-Pengujian/BAB-02-Quiz-dan-Challenge.md)

### [BAB 03: Teknik Perancangan Test Case (Black-Box & White-Box)](./BAB-03-Teknik-Perancangan-Test-Case-Black-Box-White-Box/)
- [Module 01: Black-Box Test Design: Equivalence Partitioning (EP), Boundary Value Analysis (BVA), & Decision Tables](./BAB-03-Teknik-Perancangan-Test-Case-Black-Box-White-Box/Module-01-Black-Box-Equivalence-Partitioning-BVA-Decision-Table.md)
- [Module 02: State Transition Testing, Use Case Testing, & White-Box Coverage (Statement, Branch, Path)](./BAB-03-Teknik-Perancangan-Test-Case-Black-Box-White-Box/Module-02-State-Transition-dan-White-Box-Coverage.md)
- [Praktikum Hands-on: Simulator Generator Kasus Uji BVA & Equivalence Partitioning](./BAB-03-Teknik-Perancangan-Test-Case-Black-Box-White-Box/hands-on/m01/bva_equivalence_generator_sim.js)
- [Praktikum Hands-on: Simulator State Transition Table & Code Path Coverage Engine](./BAB-03-Teknik-Perancangan-Test-Case-Black-Box-White-Box/hands-on/m02/state_transition_coverage_sim.js)
- [BAB 03 Quiz & Chapter Challenge](./BAB-03-Teknik-Perancangan-Test-Case-Black-Box-White-Box/BAB-03-Quiz-dan-Challenge.md)

### [BAB 04: Pengujian API & Validasi Kontrak Data (API Testing)](./BAB-04-Pengujian-API-dan-Validasi-Kontrak/)
- [Module 01: Fondasi REST & HTTP Testing: Request/Response, Status Codes, Header Injection, & Postman/cURL](./BAB-04-Pengujian-API-dan-Validasi-Kontrak/Module-01-Fondasi-API-Testing-HTTP-Status-Codes-Headers.md)
- [Module 02: Otomasi API Testing: JSON Schema Validation, Pact Contract Testing, & Service Virtualization](./BAB-04-Pengujian-API-dan-Validasi-Kontrak/Module-02-Otomasi-API-JSON-Schema-Validation-Mocking.md)
- [Praktikum Hands-on: Simulator API Test Runner & JSON Schema Structural Validator](./BAB-04-Pengujian-API-dan-Validasi-Kontrak/hands-on/m01/api_test_runner_schema_sim.js)
- [Praktikum Hands-on: Simulator Consumer-Driven Contract & Mocking Interceptor](./BAB-04-Pengujian-API-dan-Validasi-Kontrak/hands-on/m02/contract_testing_mock_sim.js)
- [BAB 04 Quiz & Chapter Challenge](./BAB-04-Pengujian-API-dan-Validasi-Kontrak/BAB-04-Quiz-dan-Challenge.md)

### [BAB 05: Fondasi Otomasi Pengujian & Pemrograman untuk QA](./BAB-05-Fondasi-Otomasi-Pengujian-dan-Pemrograman/)
- [Module 01: Pemrograman untuk QA (JavaScript/TypeScript): Asinkron, Rekayasa Assertion, & Error Handling](./BAB-05-Fondasi-Otomasi-Pengujian-dan-Pemrograman/Module-01-JavaScript-TypeScript-untuk-QA-Async-Assertions.md)
- [Module 02: Arsitektur Framework Otomasi: Page Object Model (POM), Screenplay Pattern, & Clean Test Code](./BAB-05-Fondasi-Otomasi-Pengujian-dan-Pemrograman/Module-02-Arsitektur-Framework-Otomasi-POM-dan-Design-Patterns.md)
- [Praktikum Hands-on: Simulator Mini Test Runner Framework & Custom Matchers](./BAB-05-Fondasi-Otomasi-Pengujian-dan-Pemrograman/hands-on/m01/mini_test_framework_sim.js)
- [Praktikum Hands-on: Simulator Page Object Model (POM) & Component Abstraction Engine](./BAB-05-Fondasi-Otomasi-Pengujian-dan-Pemrograman/hands-on/m02/page_object_model_engine_sim.js)
- [BAB 05 Quiz & Chapter Challenge](./BAB-05-Fondasi-Otomasi-Pengujian-dan-Pemrograman/BAB-05-Quiz-dan-Challenge.md)

### [BAB 06: Otomasi Pengujian Web UI Modern (Playwright & Cypress)](./BAB-06-Otomasi-Pengujian-Web-UI-Modern/)
- [Module 01: Web UI Automation dengan Playwright: Resilient Locators, Auto-Waiting, & Multi-Browser Grid](./BAB-06-Otomasi-Pengujian-Web-UI-Modern/Module-01-Playwright-Web-UI-Automation-Locators-AutoWaiting.md)
- [Module 02: Skenario Kompleks: Handling Iframes, Shadow DOM, Storage State Re-use, & Network Route Mocks](./BAB-06-Otomasi-Pengujian-Web-UI-Modern/Module-02-Advanced-Web-Testing-Iframes-ShadowDOM-NetworkMocks.md)
- [Praktikum Hands-on: Simulator Headless Web Test Runner & Auto-Wait Predicate Engine](./BAB-06-Otomasi-Pengujian-Web-UI-Modern/hands-on/m01/playwright_headless_runner_sim.js)
- [Praktikum Hands-on: Simulator Shadow DOM Traverser & Storage State Injector](./BAB-06-Otomasi-Pengujian-Web-UI-Modern/hands-on/m02/shadow_dom_storage_injector_sim.js)
- [BAB 06 Quiz & Chapter Challenge](./BAB-06-Otomasi-Pengujian-Web-UI-Modern/BAB-06-Quiz-dan-Challenge.md)

### [BAB 07: Pengujian Database, Integritas Data, & Test Data Management (TDM)](./BAB-07-Pengujian-Database-dan-Test-Data-Management/)
- [Module 01: Database Testing: Validasi Transaksi ACID, Kueri SQL Verifikasi Data, & Data Migration Testing](./BAB-07-Pengujian-Database-dan-Test-Data-Management/Module-01-Database-Testing-ACID-SQL-Verification-Migrations.md)
- [Module 02: Test Data Management (TDM): Synthetic Data Seeding, Masking Data Sensitif, & Database Fixtures](./BAB-07-Pengujian-Database-dan-Test-Data-Management/Module-02-Test-Data-Management-Seeding-Masking-Fixtures.md)
- [Praktikum Hands-on: Simulator SQL Data Integrity & Schema Migration Validator](./BAB-07-Pengujian-Database-dan-Test-Data-Management/hands-on/m01/sql_data_integrity_validator_sim.js)
- [Praktikum Hands-on: Simulator Synthetic Test Data Generator & PII Data Masker](./BAB-07-Pengujian-Database-dan-Test-Data-Management/hands-on/m02/synthetic_data_pii_masker_sim.js)
- [BAB 07 Quiz & Chapter Challenge](./BAB-07-Pengujian-Database-dan-Test-Data-Management/BAB-07-Quiz-dan-Challenge.md)

### [BAB 08: Pengujian Performa & Beban Sistem (Performance & Load Testing)](./BAB-08-Pengujian-Performa-dan-Beban-Sistem/)
- [Module 01: Fondasi Rekayasa Performa: Throughput (RPS), Latency, P95/P99 Percentiles, & Bottleneck Detection](./BAB-08-Pengujian-Performa-dan-Beban-Sistem/Module-01-Fondasi-Performance-Testing-Throughput-Latency-Percentiles.md)
- [Module 02: Scripting Beban dengan k6 & JMeter: Virtual Users (VU), Thresholds, Stress, Spike, & Soak Testing](./BAB-08-Pengujian-Performa-dan-Beban-Sistem/Module-02-Load-Testing-Scripting-k6-Stress-Spike-Soak.md)
- [Praktikum Hands-on: Simulator Percentile Latency Calculator (P50, P95, P99) & Histogram](./BAB-08-Pengujian-Performa-dan-Beban-Sistem/hands-on/m01/percentile_latency_calculator_sim.js)
- [Praktikum Hands-on: Simulator k6 Virtual Users Load Generator & SLA Threshold Evaluator](./BAB-08-Pengujian-Performa-dan-Beban-Sistem/hands-on/m02/k6_load_generator_threshold_sim.js)
- [BAB 08 Quiz & Chapter Challenge](./BAB-08-Pengujian-Performa-dan-Beban-Sistem/BAB-08-Quiz-dan-Challenge.md)

### [BAB 09: Pengujian Berbasis Perilaku (BDD), Mobile Testing, & Aksesibilitas](./BAB-09-Pengujian-Berbasis-Perilaku-BDD-dan-Mobile/)
- [Module 01: Behavior-Driven Development (BDD): Sintaks Gherkin (Given-When-Then), Cucumber, & Spec-as-Code](./BAB-09-Pengujian-Berbasis-Perilaku-BDD-dan-Mobile/Module-01-Behavior-Driven-Development-BDD-Gherkin-Cucumber.md)
- [Module 02: Mobile App Testing (Appium) & Aksesibilitas Web Otomatis (WCAG 2.2 & Axe-core)](./BAB-09-Pengujian-Berbasis-Perilaku-BDD-dan-Mobile/Module-02-Mobile-Testing-Appium-dan-Aksesibilitas-AxeCore.md)
- [Praktikum Hands-on: Simulator Gherkin BDD Feature Parser & Step Definition Matcher](./BAB-09-Pengujian-Berbasis-Perilaku-BDD-dan-Mobile/hands-on/m01/gherkin_bdd_parser_sim.js)
- [Praktikum Hands-on: Simulator Mobile Touch Gestures & Axe-Core Accessibility Engine](./BAB-09-Pengujian-Berbasis-Perilaku-BDD-dan-Mobile/hands-on/m02/mobile_gesture_axe_auditor_sim.js)
- [BAB 09 Quiz & Chapter Challenge](./BAB-09-Pengujian-Berbasis-Perilaku-BDD-dan-Mobile/BAB-09-Quiz-dan-Challenge.md)

### [BAB 10: CI/CD Integration, Flaky Test Management, & Quality Gates](./BAB-10-CICD-Integration-Flaky-Test-dan-Quality-Gates/)
- [Module 01: Integrasi Pipeline CI/CD: GitHub Actions, Parallel Execution, Test Sharding, & Matrix Builds](./BAB-10-CICD-Integration-Flaky-Test-dan-Quality-Gates/Module-01-CI-CD-Testing-Pipeline-GitHub-Actions-Parallel-Sharding.md)
- [Module 02: Mitigasi Flaky Tests, Reporting Dashboard (Allure), Quality Gates, & Shift-Left Culture](./BAB-10-CICD-Integration-Flaky-Test-dan-Quality-Gates/Module-02-Flaky-Test-Mitigation-Allure-Reporting-Quality-Gates.md)
- [Praktikum Hands-on: Simulator CI/CD Test Sharding & Matrix Execution Coordinator](./BAB-10-CICD-Integration-Flaky-Test-dan-Quality-Gates/hands-on/m01/cicd_test_sharding_matrix_sim.js)
- [Praktikum Hands-on: Simulator Flaky Test Quarantiner & Quality Gate Enforcement](./BAB-10-CICD-Integration-Flaky-Test-dan-Quality-Gates/hands-on/m02/flaky_test_quarantine_gate_sim.js)
- [BAB 10 Quiz & Chapter Challenge](./BAB-10-CICD-Integration-Flaky-Test-dan-Quality-Gates/BAB-10-Quiz-dan-Challenge.md)

---

## 🏆 [CAPSTONE PROJECT: Enterprise Omnichannel Quality Engineering Suite](./CAPSTONE-PROJECT-Enterprise-Omnichannel-Quality-Engineering.md)
Arsitektur dan implementasi suite pengujian kualitas otomatis terpadu untuk platform FinTech / E-Commerce kelas enterprise:
- **Web UI Automation Suite**: E2E multi-browser checkout flow menggunakan Playwright.
- **API & Data Contract Engine**: Validasi JSON Schema dan contract-driven test.
- **Database Consistency Verification**: Pengujian atomisitas transaksi SQL dan pencegahan race condition.
- **Performance Stress & Spike Testing**: Pengujian beban 10.000 virtual users dengan k6 threshold.
- **CI/CD Quality Gate Pipeline**: Integrasi GitHub Actions dengan mitigasi flaky test otomatis dan visual HTML reporting.
