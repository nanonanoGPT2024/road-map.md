# BAB 10: Dokumentasi Arsitektur, ADR, & Governance
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mengonseptualisasikan dan Mengimplementasikan Architecture as Code (AaC):** Menerjemahkan aturan arsitektur abstrak ke dalam *executable fitness functions* menggunakan framework verifikasi arsitektur statis (*static architecture verification*).
2. **Merancang Automated Architectural Governance Pipeline:** Membangun *continuous governance gate* di CI/CD yang memvalidasi *Architectural Decision Records* (ADR), model C4, dan dependensi kode secara otomatis untuk mencegah *architectural drift*.
3. **Mengorkestrasi Living Documentation System:** Mengintegrasikan model arsitektur deklaratif (seperti Structurizr DSL) dengan *developer portal* enterprise (seperti Backstage) dan *version control system*.
4. **Mengelola Siklus Hidup ADR Tingkat Lanjut:** Mengotomatiskan manajemen status, dependensi, dan *superseding lifecycle* dari puluhan hingga ratusan ADR di lingkungan *multi-repo* dan *monorepo*.
5. **Menerapkan Deteksi dan Remedi Drift Arsitektur:** Mengidentifikasi pelanggaran batas modularitas (*boundary violations*) dan siklus dependensi terlarang (*forbidden cyclic dependencies*) sebelum mencapai tahap produksi.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Fondasi ADR dasar (Format Nygard, MADR) dan dasar-dasar C4 Model (Context, Container, Component, Code).
* Pengalaman praktis dalam pengembangan berorientasi objek atau modular (Java, TypeScript, Go, atau C#).
* Pemahaman mendalam mengenai arsitektur berlapis (*Layered Architecture*), *Hexagonal/Ports and Adapters*, dan *Clean Architecture*.
* Kemahiran dalam mengonfigurasi *CI/CD pipelines* (GitHub Actions, GitLab CI, atau Jenkins).
* Penguasaan dasar *Static Code Analysis* (AST, Dependency Graphing).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Architectural Governance Engine & Fitness Functions
Dalam skala enterprise, dokumentasi pasif dalam format wiki atau PDF statis selalu berujung pada *documentation rot* (kondisi di mana dokumentasi tidak lagi mencerminkan sistem riil). Pendekatan *Evolutionary Architecture* memecahkan masalah ini dengan memperkenalkan konsep **Architectural Fitness Functions**: fungsi pengujian otomatis yang mengevaluasi integritas arsitektur terhadap batas-batas yang telah disepakati.

```
       +-------------------------------------------------------------+
       |                  DEVELOPER COMMIT / PR                      |
       +-------------------------------------------------------------+
                                      |
                                      v
       +-------------------------------------------------------------+
       |               CI/CD ARCHITECTURE GOVERNANCE GATE            |
       |                                                             |
       |  +--------------------+  +-------------------------------+  |
       |  | Static ADR Linting |  | Architectural Fitness Tests   |  |
       |  | (Schema, Metadata, |  | (ArchUnit / Dependency Cruiser|  |
       |  |  State Transitions)|  |  Layer Isolation, Cycles)     |  |
       |  +--------------------+  +-------------------------------+  |
       |            |                             |                  |
       |            +--------------+--------------+                  |
       |                           |                                 |
       |                           v                                 |
       |  +-------------------------------------------------------+  |
       |  | C4 Model Parsing & Verification (Structurizr CLI)     |  |
       |  | - Validasi sinkronisasi relasi Container & Component  |  |
       |  +-------------------------------------------------------+  |
       +-------------------------------------------------------------+
                                      |
                 +--------------------+--------------------+
                 |                                         |
             [PASSED]                                  [FAILED]
                 |                                         |
                 v                                         v
   +---------------------------+             +---------------------------+
   | Build & Deploy Artifacts  |             | Block PR Merge            |
   | Export Living Doc to Portal|            | Return Diagnostics Log    |
   +---------------------------+             +---------------------------+
```

Fitness functions beroperasi di tingkat AST (*Abstract Syntax Tree*) dan *bytecode analysis*. Alih-alih mengecek kebenaran logika bisnis (*unit test*), engine ini mengevaluasi:
1. **Aferen ($C_a$) dan Eferen ($C_e$) Coupling:** Mengukur kestabilan modul berdasarkan relasi masuk dan keluar.
2. **Instability ($I$):** Rasio $I = \frac{C_e}{C_a + C_e}$. Aturan arsitektur menentukan apakah modul inti (*core domain*) memiliki $I \approx 0$ (sangat stabil) dan modul infrastruktur memiliki $I \approx 1$.
3. **Abstraksi ($A$):** Rasio kelas abstrak/antarmuka terhadap total kelas.
4. **Distance from the Main Sequence ($D$):** $D = |A + I - 1|$. Mengukur apakah modul jatuh ke dalam *Zone of Pain* (terlalu kaku, sulit diubah) atau *Zone of Uselessness* (terlalu abstrak tanpa implementasi).

#### ADR Metamodel dan Directed Acyclic Graph (DAG)
Dalam arsitektur modern, ADR bukan sekadar file teks bebas, melainkan simpul (*node*) dalam sebuah graf berarah (*Directed Graph*). Sebuah keputusan arsitektur sering kali memodifikasi, memperluas, atau menganulir (*supersede*) keputusan sebelumnya.

```
  +-----------+           amends           +-----------+
  |  ADR-001  | <------------------------ |  ADR-008  |
  | Event Bus |                            | Schema Reg|
  +-----------+                            +-----------+
        ^
        | supersedes
  +-----------+
  |  ADR-014  |
  | Kafka Strm|
  +-----------+
```

Jika struktur ini dikelola secara manual, metadata hubungan antar-keputusan akan cepat rusak. Oleh karena itu, *ADR Engine* internal harus menerapkan *Schema Validation* (menggunakan JSON Schema atau YAML Frontmatter parsing) yang memvalidasi bahwa:
* Status mutasi ADR adalah *state machine* yang valid: `PROPOSED` $\rightarrow$ `ACCEPTED` $\rightarrow$ (`SUPERSEDED` | `DEPRECATED`).
* Setiap referensi ke ADR lain (`supersedes: ADR-001`) memiliki *reciprocal pointer* pada berkas target yang diperbarui secara atomik.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Passive Docs) | Pendekatan Enterprise (Active Architecture as Code) |
| :--- | :--- | :--- |
| **Lokasi Kebenaran (*Source of Truth*)** | Confluence, Google Docs, Word terisolasi. | Berada di repositori Git bersama kode sumber (*In-repo Documentation*). |
| **Mekanisme Validasi** | *Manual Architecture Review Board* (ARB) sporadis. | Otomatis di CI/CD melalui *Architecture Fitness Functions*. |
| **Pembaruan Diagram** | Menggambar ulang manual di Visio, Lucidchart. | *Text-based Model-driven generation* (PlantUML, Structurizr DSL). |
| **Visibilitas Pelanggaran** | Terdeteksi di produksi saat modul saling mengunci (*deadlock/spaghetti*). | Terdeteksi saat kompilasi atau eksekusi *pull request test suite*. |
| **Tata Kelola ADR** | Dibuat sekali saat proyek dimulai, lalu dilupakan. | Mengatur siklus hidup keputusan arsitektur secara terstruktur dan terhubung langsung dengan *tracing commit*. |

#### Mengapa Active Governance Wajib di Level Enterprise?
1. **Mencegah Erosi Arsitektur (*Architectural Drift*):** Developer di bawah tekanan tenggat waktu sering kali mengambil jalan pintas dengan mengimpor paket infrastruktur (misalnya database driver atau framework Web) langsung ke lapisan domain logic. Tanpa *fitness functions*, erosi ini tak terdeteksi hingga sistem menjadi *monolith* kusut yang tak dapat diuji.
2. **Auditabilitas dan Kepatuhan Regulasi:** Industri FinTech, Kesehatan, dan Sistem Kritis menuntut bukti kepatuhan keamanan dan desain sistem (misalnya: "Apakah enkripsi diterapkan di semua titik transfer data?"). ADR yang tervalidasi di Git menyediakan jejak audit forensik yang *immutable*.

---

### 5. How (Workflow Detail)

Siklus hidup implementasi tata kelola arsitektur mencakup langkah-langkah berikut:

1. **Fase Inisiasi (RFC - Request for Comments):**
   * Arsitek atau Tech Lead membuat *Pull Request* baru yang berisi dokumen ADR dengan status `PROPOSED`.
   * Template ADR menggunakan format terstruktur berbasis *machine-readable frontmatter*.

2. **Fase Otomasi Verifikasi (PR Gatekeeper):**
   * Linter mengecek kesesuaian skema ADR (kelengkapan konteks, konsekuensi, dan status).
   * Generator dokumen merender diagram C4 dari Structurizr DSL dan membandingkannya dengan definisi infrastruktur riil.
   * Tool verifikasi arsitektur (misal: ArchUnit) memindai kode untuk memastikan tidak ada pelanggaran terhadap ADR yang sedang diusulkan atau yang telah diterima sebelumnya.

3. **Fase Persetujuan & Penggabungan (*Consensus & Merge*):**
   * Minimal $N$ persetujuan dari tim arsitektur (*Architecture Review Board* / Staff Engineers).
   * Status ADR diperbarui menjadi `ACCEPTED`.
   * CI Pipeline mengekspor model arsitektur dan ADR ke portal dokumentasi internal (misalnya Backstage Software Catalog).

4. **Fase Runtime & Pemeliharaan Berkelanjutan:**
   * Jika ada keputusan baru yang menggantikan keputusan lama, *ADR Graph Validator* memastikan status ADR lama diubah menjadi `SUPERSEDED` dan menunjuk ke ADR baru secara otomatis.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan membangun gedung pencakar langit. 
* **Dokumentasi Pasif:** Cetak biru (*blueprint*) digambar sekali, lalu disimpan di laci kantor direksi. Tukang bangunan di lantai 40 memasang pipa gas sembarangan menembus kolom struktural penopang beban. Tidak ada yang tahu sampai gedung retak dan runtuh.
* **Architecture as Code (Active):** Setiap kali tukang memasang balok atau pipa baru, sensor laser otomatis memindai struktur fisik terhadap model 3D digital (*Building Information Modeling* - BIM). Jika pipa menembus kolom penopang beban, alarm otomatis berbunyi, lift material terkunci, dan konstruksi dihentikan seketika sampai rancangan pipa diperbaiki.

#### Diagram Interaksi Fitness Function & ADR Governance

```
+---------------------------------------------------------------------------------------+
| REPOSITORY MONOREPO / SERVICES                                                        |
|                                                                                       |
|  docs/adr/                                     src/main/                              |
|  +--------------------+                        +-----------------------------------+  |
|  | 0001-hexagonal.md  |                        | com.enterprise.order              |  |
|  | status: ACCEPTED   |                        |  ├── domain/         (Pure Logic) |  |
|  +--------------------+                        |  ├── application/    (Use Cases)  |  |
|            |                                   |  ├── infrastructure/ (Adapters)   |  |
|            | Validates Intent                  |  └── presentation/   (Controllers)|  |
|            v                                   +-----------------------------------+  |
|  +--------------------+                                          |                    |
|  | ArchUnit Rule Suite|<-----------------------------------------+                    |
|  | (Fitness Function) | Reads Classpath Dependencies                                  |
|  +--------------------+                                                               |
+------------|--------------------------------------------------------------------------+
             |
             v
+---------------------------------------------------------------------------------------+
| EXECUTION EVALUATION ENGINE                                                           |
|                                                                                       |
| Rule: "Domain classes should not depend on Infrastructure classes"                    |
|                                                                                       |
| [AST Parser] -> Evaluates com.enterprise.order.domain.Order                          |
|                 -> Checks imports:                                                    |
|                    - java.time.Instant            -> OK                               |
|                    - org.postgresql.Driver        -> VIOLATION! (Drift detected)      |
|                                                                                       |
| RESULT: BUILD FAILURE. Merge denied.                                                  |
+---------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Validasi Skema ADR dengan Skrip Node.js
Skrip ini memverifikasi bahwa berkas ADR memiliki metadata YAML Frontmatter yang valid dan status yang sah.

```javascript
// scripts/validate-adr.js
const fs = require('fs');
const path = require('path');
const matter = require('gray-matter');

const ADR_DIR = path.join(__dirname, '../docs/adr');
const VALID_STATUSES = ['PROPOSED', 'ACCEPTED', 'REJECTED', 'SUPERSEDED', 'DEPRECATED'];

function validateADRs() {
  const files = fs.readdirSync(ADR_DIR).filter(file => file.endsWith('.md'));
  let hasError = false;

  files.forEach(file => {
    const filePath = path.join(ADR_DIR, file);
    const content = fs.readFileSync(filePath, 'utf-8');
    const parsed = matter(content);

    // Validasi Metadata
    if (!parsed.data.id || !parsed.data.title || !parsed.data.status || !parsed.data.date) {
      console.error(`[INVALID METADATA] File: ${file} harus memiliki id, title, status, dan date.`);
      hasError = true;
    }

    if (!VALID_STATUSES.includes(parsed.data.status)) {
      console.error(`[INVALID STATUS] File: ${file} memiliki status tidak valid: ${parsed.data.status}`);
      hasError = true;
    }

    if (parsed.data.status === 'SUPERSEDED' && !parsed.data.superseded_by) {
      console.error(`[MISSING LINK] File: ${file} berstatus SUPERSEDED tapi tidak mendeklarasikan 'superseded_by'.`);
      hasError = true;
    }
  });

  if (hasError) {
    process.exit(1);
  } else {
    console.log(`Pemeriksaan selesai: ${files.length} ADR valid.`);
  }
}

validateADRs();
```

#### B. Practical Example: Production-Ready Architectural Fitness Functions (ArchUnit)
Implementasi pengujian integritas arsitektur Hexagonal tingkat produksi menggunakan ArchUnit di ekosistem enterprise Java/Kotlin.

```java
package com.enterprise.architecture.governance;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.lang.ArchRule;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.Architectures.onionArchitecture;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

public class ArchitectureComplianceTest {

    private static JavaClasses importedClasses;

    @BeforeAll
    static void setup() {
        importedClasses = new ClassFileImporter()
                .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
                .importPackages("com.enterprise.order");
    }

    @Test
    @DisplayName("ADR-004: Pola Hexagonal/Clean Architecture harus dihormati secara mutlak")
    void verifyHexagonalArchitectureLayers() {
        ArchRule layerRule = onionArchitecture()
                .domainModels("com.enterprise.order.domain.model..")
                .domainServices("com.enterprise.order.domain.service..")
                .applicationServices("com.enterprise.order.application..")
                .adapter("persistence", "com.enterprise.order.infrastructure.persistence..")
                .adapter("rest", "com.enterprise.order.infrastructure.rest..")
                .adapter("messaging", "com.enterprise.order.infrastructure.messaging..");

        layerRule.check(importedClasses);
    }

    @Test
    @DisplayName("ADR-009: Domain Model tidak boleh memiliki dependensi ke framework luar")
    void domainModelMustRemainPure() {
        ArchRule pureDomainRule = noClasses()
                .that().resideInAPackage("..domain.model..")
                .should().dependOnClassesThat()
                .resideInAnyPackage(
                        "org.springframework..",
                        "javax.persistence..",
                        "jakarta.persistence..",
                        "com.fasterxml.jackson.."
                )
                .because("Domain model harus bebas dari framework leaks (Sesuai ADR-009)");

        pureDomainRule.check(importedClasses);
    }

    @Test
    @DisplayName("Governance: Tidak boleh ada cyclic dependencies antar sub-paket modul")
    void verifyNoCyclicDependencies() {
        ArchRule noCycles = slices()
                .matching("com.enterprise.order.(*)..")
                .should().beFreeOfCycles()
                .because("Siklus dependensi menyebabkan tight coupling dan memecah modularitas");

        noCycles.check(importedClasses);
    }

    @Test
    @DisplayName("ADR-015: Penamaan Interface Ports dan Implemenations Adapter")
    void portsMustBeInterfaces() {
        ArchRule portRules = classes()
                .that().resideInAPackage("..domain.port..")
                .should().beInterfaces()
                .because("Semua Ports pada domain layer harus berupa antarmuka murni");

        portRules.check(importedClasses);
    }
}
```

#### C. Structurizr DSL untuk C4 Model as Code
Berkas deklaratif model C4 yang dapat diekspor menjadi SVG/PlantUML secara deterministik di CI/CD.

```dsl
// docs/architecture/workspace.dsl
workspace "Enterprise Payment System" "Model Arsitektur Produksi" {

    model {
        customer = person "Nasabah Retail" "Pengguna aplikasi mobile banking."
        
        enterpriseSystem = softwareSystem "Core Payment Platform" "Memproses transaksi pembayaran instan." {
            apiGateway = container "API Gateway" "Mengarahkan dan mengamankan lalu lintas API." "Kong / NGINX"
            
            paymentService = container "Payment Orchestrator" "Mengelola alur kerja transaksi pembayaran." "Java / Spring Boot" {
                paymentController = component "Payment REST Controller" "Menerima request transaksi." "Spring MVC Rest"
                paymentHandler = component "Payment Domain Handler" "Eksekusi state machine transaksi." "Domain Service"
                accountRepo = component "Account Repository Port" "Abstraksi akses akun nasabah." "Interface"
            }
            
            database = container "Transaction Ledger DB" "Menyimpan data transaksi finansial secara ACID." "PostgreSQL" "Database"
        }

        // Hubungan antar elemen
        customer -> apiGateway "Mengirimkan instruksi transfer via HTTPS"
        apiGateway -> paymentController "Meneruskan request transfer [JSON/REST]"
        paymentController -> paymentHandler "Memanggil eksekusi pembayaran"
        paymentHandler -> accountRepo "Membaca saldo dan validasi akun"
        accountRepo -> database "Menyimpan mutasi transaksi [JDBC]"
    }

    views {
        systemContext enterpriseSystem "SystemContext" {
            include *
            autoLayout lr
        }

        container enterpriseSystem "Containers" {
            include *
            autoLayout lr
        }

        component paymentService "Components" {
            include *
            autoLayout lr
        }

        theme default
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Skala FinTech "PayNusantara"
PayNusantara bermigrasi dari monolit berbasis Ruby on Rails ke arsitektur *distributed services* (45 microservices) dengan throughput rata-rata 12.000 transaksi per detik (TPS). Tim rekayasa perangkat lunak bertambah dari 25 engineer menjadi 230 engineer dalam waktu 18 bulan, tersebar di 14 *squad*.

#### Masalah (The Breakdown)
1. **Architectural Rot Eksplosif:** Berbagai tim membuat variasi komunikasi antar-service sendiri-sendiri (gRPC, REST, Kafka, RabbitMQ, bahkan koneksi database silang antar-service).
2. **Ghost ADR:** Terdapat 67 dokumen ADR di Google Drive yang tidak pernah dibaca oleh para engineer baru. Akibatnya, tim Checkout melanggar ADR-012 (tentang larangan *Distributed 2-Phase Commit*) dan membangun pola transaksi yang mengakibatkan *cascading lockups* saat *flash sale*.
3. **Database Sharing Incident:** Tim Loyalitas mengakses langsung database `Transactions` melalui *read-replica*, mengabaikan kontrak domain API dan menyebabkan migrasi skema database utama terhambat selama 6 bulan.

#### Solusi Arsitektur
1. **Migrasi Repositori Dokumen:** Seluruh ADR dipindahkan ke repositori Git masing-masing di bawah folder `/docs/adr` menggunakan format standar Frontmatter.
2. **Penerapan Automated CI Gates:**
   * Diintegrasikan ArchUnit (untuk service Java/Kotlin) dan Dependency-Cruiser (untuk service Node.js/TypeScript) ke dalam pipeline GitHub Actions.
   * Pull Request otomatis ditolak jika:
     * Ditemukan koneksi DB langsung di luar modul service yang berwenang.
     * Tidak ada file ADR berstatus `PROPOSED` atau `ACCEPTED` yang disertakan saat menambahkan modul baru.
3. **Sentralisasi C4 Living Documentation via Structurizr DSL:**
   * Setiap service mempublikasikan `workspace.dsl` lokal mereka.
   * Sebuah job orkestrasi CI pusat mengagregasikan seluruh file DSL setiap malam untuk menghasilkan Diagram Arsitektur C4 enterprise yang terintegrasi di portal Backstage.

#### Dampak (Metrics)
* **Zero Cross-Database Coupling:** 100% dependensi silang database tereliminasi dalam 3 bulan.
* **Lead Time to Architecture Review:** Berkurang dari 14 hari kerja (melalui rapat Architecture Review Board manual yang lambat) menjadi **2 hari** (melalui validasi terotomatisasi di PR dan *asynchronous RFC review*).
* **Onboarding Speed:** Waktu rata-rata bagi engineer baru untuk melakukan commit pertama yang memenuhi standar arsitektur turun dari **21 hari menjadi 5 hari**.

---

### 9. Trade-offs

Mengadopsi tata kelola arsitektur berbasis kode melibatkan kompromi teknis yang signifikan:

| Parameter | Pendekatan Longgar / Manual | Architecture-as-Code & Strict Governance | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Kecepatan Build CI (*Build Latency*)** | Cepat (hanya unit test fungsional). | Tambahan waktu 1.5 - 5 menit untuk AST parsing, refleksi, dan kompilasi rule. | Peningkatan latensi CI dapat memengaruhi frekuensi merge. Mitigasi: Jalankan fitness tests berat secara paralel atau pada tahap *Pre-merge PR*, bukan pada setiap commit branch lokal. |
| **Fleksibilitas Developer (*Velocity*)** | Sangat tinggi di awal. Developer bebas menulis kode apa saja. | Lebih rendah di awal. PR diblokir jika melanggar boundary. | Menurunkan kecepatan prototyping jangka pendek, namun mengeliminasi biaya refactoring besar (*technical debt*) di masa depan secara eksponensial. |
| **Beban Pemeliharaan (*Maintenance Overhead*)** | Rendah di awal, sangat tinggi di akhir akibat technical debt. | Diperlukan pemeliharaan berkelanjutan terhadap skrip validasi, aturan ArchUnit, dan file DSL. | Jika aturan arsitektur terlalu kaku (misalnya terlalu banyak rule penamaan kelas), aturan tersebut menjadi beban birokrasi kode (*brittle tests*). |
| **Kurva Belajar Tim (*Learning Curve*)** | Hampir tidak ada (hanya baca dokumen jika ingat). | Tinggi. Engineer harus memahami konsep seperti Inversion of Control, Couplings Metrics, dan DSL syntax. | Membutuhkan pelatihan menyeluruh dan contoh kode referensi (*gold-standard templates*) sebelum aturan diaktifkan sebagai *blocking gate*. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: Aturan Arsitektur yang Terlalu Rapuh (*Brittle Fitness Functions*)
* **Kasus:** Menulis fitness function yang mencocokkan penamaan string kelas secara spesifik, misalnya: `classes().that().haveSimpleNameEndingWith("ServiceImpl").should()...`
* **Gejala:** Refactoring sederhana pada nama kelas mematahkan build arsitektur, menimbulkan frustrasi di tim.
* **Solusi:** Gunakan penandaan berbasis anotasi atau struktur paket modular (*package namespace*), alih-alih konvensi penamaan string kaku.
  ```java
  // Lebih baik: Berbasis Anotasi Domain
  classes().that().areAnnotatedWith(DomainService.class)
           .should().resideInAPackage("..domain.service..");
  ```

#### 2. Kesalahan: Status ADR "Zombi" (Tidak Pernah Diperbarui)
* **Kasus:** Sebuah keputusan baru diambil yang membatalkan ADR-003, tetapi file ADR-003 tidak pernah dimutasi menjadi `SUPERSEDED`.
* **Gejala:** Developer baru membaca ADR-003 dan mengimplementasikan pola yang sudah usang.
* **Solusi:** Buat rule CI pada linter ADR: jika sebuah ADR baru mengklaim menggantikan ADR lama (`supersedes: ADR-003`), skrip verifikasi harus memvalidasi bahwa file `0003-xxx.md` juga ikut diubah dalam *Pull Request* yang sama dengan status `SUPERSEDED` dan referensi `superseded_by: ADR-baru`.

#### 3. Kesalahan: Memory Leak / Timeout saat ArchUnit Memindai Repositori Monolitik
* **Kasus:** Memindai ribuan file class sekaligus tanpa filtering path.
* **Gejala:** `OutOfMemoryError: Java heap space` saat eksekusi test CI.
* **Solusi:** Gunakan `ImportOption` untuk mengecualikan modul pihak ketiga, pustaka mock, dan file autogenerated (seperti Protobuf atau GraphQL generated classes).
  ```java
  new ClassFileImporter()
      .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
      .withImportOption(location -> !location.contains("/generated/"))
      .importPackages("com.enterprise.app");
  ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini untuk mengaudit kematangan sistem dokumentasi dan tata kelola arsitektur Anda:

- [ ] **Git-Co-located Architecture:** ADR dan file DSL arsitektur tersimpan di repositori yang sama dengan kode sumber aplikasi.
- [ ] **Deterministic Linting:** ADR mematuhi format Markdown + Frontmatter tervalidasi skema otomatis di CI (termasuk kelengkapan metadata: `id`, `title`, `date`, `status`, `authors`, `context`, `decision`, `consequences`).
- [ ] **Atomic ADR State Mutation:** Setiap mutasi status ADR (`SUPERSEDED` / `DEPRECATED`) diverifikasi secara atomik dalam satu Pull Request bersama perubahan fungsionalnya.
- [ ] **Automated Boundary Verification:** Batasan arsitektur (Ports, Adapters, Domain Core) diverifikasi oleh static code fitness functions (ArchUnit, Depend-o-meter, dsb.) pada pipeline pull request.
- [ ] **Cyclic Dependency Zero-Tolerance:** Tidak ada ketergantungan siklis pada tingkat paket (`package level`) maupun tingkat container/service.
- [ ] **Headless C4 Rendering:** C4 Diagram digenerasi otomatis menjadi artefak visual (PNG/SVG) dari Structurizr DSL setiap kali branch utama diperbarui.
- [ ] **Internal Portal Sync:** Dokumentasi arsitektur di-publish secara otomatis ke platform developer enterprise (Backstage, Confluence via API, atau static site generator).
- [ ] **Architectural Coverage Metric:** Setidaknya 100% core domain logic bebas dari impor dependensi eksternal/framework yang tidak disetujui.

---

### 12. Hands-on Practice

Buat dan jalankan sistem automated governance minimal di lokal Anda di direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Struktur Proyek
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/docs/adr
mkdir -p hands-on/m02/scripts
cd hands-on/m02
npm init -y
npm install gray-matter js-yaml
```

#### Langkah 2: Buat Skema ADR & Validator Script
Buat file `scripts/verify-governance.js`:

```javascript
const fs = require('fs');
const path = require('path');
const matter = require('gray-matter');

const ADR_DIR = path.join(__dirname, '../docs/adr');

function runAudit() {
    console.log(">> Memulai Audit Governance Arsitektur...");
    const files = fs.readdirSync(ADR_DIR).filter(f => f.endsWith('.md'));
    
    if (files.length === 0) {
        console.error("FAILED: Tidak ada ADR yang ditemukan!");
        process.exit(1);
    }

    const adrRegistry = new Map();

    // Pass 1: Parse and validate format
    files.forEach(file => {
        const fullPath = path.join(ADR_DIR, file);
        const fileContent = fs.readFileSync(fullPath, 'utf8');
        const { data, content } = matter(fileContent);

        if (!data.id || !data.status || !data.title) {
            console.error(`FAILED: ADR ${file} kekurangan metadata wajib (id, status, title).`);
            process.exit(1);
        }

        adrRegistry.set(data.id, { ...data, file, rawContent: content });
    });

    // Pass 2: Validate State Links
    adrRegistry.forEach((adr, id) => {
        if (adr.status === 'SUPERSEDED') {
            if (!adr.superseded_by || !adrRegistry.has(adr.superseded_by)) {
                console.error(`FAILED: ADR-${id} berstatus SUPERSEDED, tetapi 'superseded_by' (${adr.superseded_by}) tidak terdaftar!`);
                process.exit(1);
            }
        }
    });

    console.log(`SUCCESS: Total ${adrRegistry.size} ADR terverifikasi secara valid.`);
}

runAudit();
```

#### Langkah 3: Buat Berkas Contoh ADR
Buat file `docs/adr/0001-record-architecture-decisions.md`:

```markdown
---
id: 1
title: Penggunaan Architecture Decision Records
status: SUPERSEDED
superseded_by: 2
date: 2026-01-10
---

# 1. Penggunaan Architecture Decision Records

## Konteks
Kami membutuhkan cara terstandarisasi untuk mendokumentasikan keputusan arsitektur tim.

## Keputusan
Kami mencatat keputusan arsitektur menggunakan teks biasa di wiki.

## Konsekuensi
Dokumentasi di wiki menjadi usang karena tidak berada di repositori kode.
```

Buat file `docs/adr/0002-active-adr-governance-in-git.md`:

```markdown
---
id: 2
title: Active ADR Governance dalam Repositori Git
status: ACCEPTED
supersedes: 1
date: 2026-03-15
---

# 2. Active ADR Governance dalam Repositori Git

## Konteks
ADR di wiki gagal dipertahankan dan mengakibatkan documentation rot.

## Keputusan
Menyimpan ADR langsung di direktori Git (`docs/adr/`) dengan frontmatter metadata termonitor di CI/CD.

## Konsekuensi
Setiap arsitektur baru memerlukan commit ADR dan lolos validasi pipeline.
```

#### Langkah 4: Jalankan Pemeriksaan
```bash
node scripts/verify-governance.js
```
*Output yang Diharapkan:*
```text
>> Memulai Audit Governance Arsitektur...
SUCCESS: Total 2 ADR terverifikasi secara valid.
```

Uji kegagalan dengan mengganti `superseded_by: 99` pada `0001-record-architecture-decisions.md` dan jalankan kembali script untuk melihat bagaimana CI mendeteksi *broken reference*.

---

### 13. Exercise

#### Tingkat: Easy
Tuliskan sebuah skrip validator (Python atau Node.js) yang memverifikasi bahwa file Markdown ADR harus memiliki 3 bagian heading wajib: `## Konteks`, `## Keputusan`, dan `## Konsekuensi`. Skrip harus memicu *exit code* 1 jika salah satu bagian tidak ditemukan.

#### Tingkat: Medium
Konfigurasikan sebuah rule pada ArchUnit atau TypeScript `dependency-cruiser` yang memblokir modul presentasi (`presentation`/`controller`) agar tidak dapat mengakses *Database Entity* atau *Repository* secara langsung, melainkan wajib melalui *Application Service / Use Case Layer*.

#### Tingkat: Hard
Rancang dan buat skrip CI workflow (GitHub Actions syntax) yang mengekstrak diff Git pada suatu PR, mendeteksi jika ada file baru di path `src/infrastructure/` tanpa disertai penambahan atau pengubahan berkas di path `docs/adr/`, lalu memberikan *automated comment* pada PR tersebut serta membatalkan proses *merge*.

---

### 14. Challenge

**Skenario:**
Sebuah platform perbankan multinasional memiliki monorepo yang berisi 3 domain utama: `Core-Banking`, `Wealth-Management`, dan `Compliance`. Tim arsitektur telah menetapkan aturan tata kelola absolut:
1. `Wealth-Management` boleh memanggil antarmuka publik dari `Core-Banking`, tetapi dilarang keras mengimpor model internalnya.
2. `Core-Banking` sama sekali tidak boleh memiliki dependensi balik (*zero backward dependency*) ke `Wealth-Management` maupun `Compliance`.
3. Komponen `Compliance` wajib menyadap semua *Domain Event* dari kedua modul lain, namun tidak boleh memodifikasi status data modul tersebut.

**Tugas Anda:**
Rancang arsitektur implementasi fitness function terdistribusi menggunakan ArchUnit atau AST Parser kustom yang:
* Dapat dieksekusi dalam waktu kurang dari 60 detik untuk 1,5 juta baris kode.
* Menghasilkan laporan metrik $D$ (*Distance from the Main Sequence*) untuk setiap modul.
* Memiliki kemampuan memvalidasi hubungan ketergantungan ini secara deterministik pada branch PR sebelum di-merge ke branch utama.
* Susun spesifikasi teknis lengkap, deklarasi rule, dan mitigasi bottleneck performa analisis statisnya.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konsep Dasar (Basic)
1. **Apa perbedaan mendasar antara *Passive Documentation* dan *Active Architectural Governance*?**
   * A. Passive documentation menggunakan format Word, sedangkan active menggunakan Excel.
   * B. Passive documentation tidak divalidasi oleh sistem, sedangkan active documentation diverifikasi secara terprogram oleh fitness functions di CI/CD.
   * C. Passive documentation ditulis oleh engineer, active documentation ditulis otomatis oleh AI.
   * D. Passive documentation bersifat internal, active documentation disebarkan ke publik.
   * *Jawaban yang benar:* B. Active architecture governance mengandalkan eksekusi automated test/rules pada CI pipeline untuk memvalidasi integritas rancangan terhadap kode riil.

2. **Apa yang dimaksud dengan *Architectural Fitness Function*?**
   * A. Fungsi kode untuk mengukur performa CPU dan memori saat load testing.
   * B. Metrik untuk menghitung jumlah baris kode yang ditulis oleh arsitek.
   * C. Pengujian otomatis yang mengevaluasi apakah sistem memenuhi batasan dan integritas arsitektur yang telah ditentukan.
   * D. Fungsi algoritma untuk mengoptimasi query database secara dinamis.
   * *Jawaban yang benar:* C. Sesuai konsep *Evolutionary Architecture*, fitness function mengevaluasi karakteristik integritas struktural arsitektur sistem.

3. **Status apa yang tepat untuk ADR yang digantikan oleh keputusan arsitektur yang lebih baru?**
   * A. `REJECTED`
   * B. `DEPRECATED`
   * C. `SUPERSEDED`
   * D. `ARCHIVED`
   * *Jawaban yang benar:* C. `SUPERSEDED` digunakan secara spesifik untuk keputusan yang digantikan secara langsung oleh keputusan lain.

4. **Dalam metrik kuantitatif Robert C. Martin, modul yang memiliki kestabilan mutlak ($I = 0$) berarti:**
   * A. Modul tersebut memiliki banyak dependensi eferen ($C_e > 0$) dan tidak ada dependensi aferen ($C_a = 0$).
   * B. Modul tersebut tidak bergantung pada paket lain, melainkan modul-modul lain yang bergantung padanya ($C_e = 0, C_a > 0$).
   * C. Modul tersebut sangat rapuh dan mudah berubah.
   * D. Modul tersebut tidak pernah diuji coba.
   * *Jawaban yang benar:* B. Nilai $I = \frac{C_e}{C_a + C_e} = 0$ menunjukkan modul mandiri (*independent*) yang dijadikan fondasi oleh modul lain.

5. **Apa keunggulan utama menggunakan Structurizr DSL dibandingkan alat pembuat diagram konvensional?**
   * A. Warna diagram dapat diubah otomatis setiap jam.
   * B. Model sistem didefinisikan satu kali sebagai data/kode, sedangkan visualisasi diagram C4 berbagai level dirender secara konsisten dari model tunggal tersebut.
   * C. Structurizr DSL otomatis menghasilkan source code aplikasi backend secara utuh.
   * D. Structurizr DSL tidak memerlukan compiler atau CLI.
   * *Jawaban yang benar:* B. Single source of truth berbasis model teks mencegah inkonsistensi representasi visual antar-level C4.

---

#### Bagian B: Analisis Tingkat Menengah (Intermediate)
6. **Di sebuah repositori berbasis Hexagonal Architecture, rule ArchUnit berikut mengalami kegagalan (*assertion error*):**
   ```java
   noClasses().that().resideInAPackage("..domain..")
     .should().dependOnClassesThat().resideInAPackage("..infrastructure..")
   ```
   **Apa penyebab pelanggaran ini dari perspektif desain arsitektur?**
   * A. Modul infrastruktur mengimplementasikan interface dari domain.
   * B. Domain logic mengimpor kelas konkret dari layer infrastruktur, melanggar *Dependency Inversion Principle*.
   * C. Unit testing gagal mengeksekusi method di domain.
   * D. Package name domain salah diketik di file konfigurasi ArchUnit.
   * *Jawaban yang benar:* B. Inti dari Clean/Hexagonal Architecture adalah lapisan Domain tidak boleh memiliki ketergantungan terhadap implementasi teknis eksternal (Infrastruktur).

7. **Mengapa penulisan ADR harus di-commit bersamaan dengan perubahan kode dalam Pull Request yang sama?**
   * A. Agar commit history terlihat panjang dan rapi.
   * B. Menjamin atomisitas antara keputusan dan implementasi, serta memudahkan teknik `git bisect` dan pelacakan audit di masa depan.
   * C. Menghindari pembatasan API GitHub terhadap pull request terpisah.
   * D. Agar arsitek tidak perlu membaca kode sumber.
   * *Jawaban yang benar:* B. Hubungan atomik antara kode dan dokumen mencegah inkonsistensi temporal (*code drift*).

8. **Perhatikan metrik sebuah paket: $A = 0.1$ (sangat konkret), $I = 0.05$ (sangat stabil/banyak yang bergantung padanya). Berdasarkan *Distance from the Main Sequence* ($D = |A + I - 1|$), posisi paket ini berada di:**
   * A. Main Sequence ($D \approx 0$).
   * B. Zone of Pain ($D \approx 0.85$, konkret dan sulit diubah, sehingga menjadi bottleneck perubahan).
   * C. Zone of Uselessness (terlalu abstrak tanpa implementasi).
   * D. Perfect Equilibrium.
   * *Jawaban yang benar:* B. Modul yang sangat stabil (banyak dependensi masuk) tetapi sangat konkret (tanpa abstraksi) berada di *Zone of Pain*, menjadikannya rigid dan berisiko tinggi saat harus dimodifikasi.

9. **Saat mengintegrasikan Structurizr DSL dengan Backstage, mekanisme terbaik untuk menjaga sinkronisasi model arsitektur adalah:**
   * A. Mengunggah screenshot diagram secara manual ke halaman Confluence mingguan.
   * B. Menjalankan pipeline CI pada event `push` ke branch utama untuk mengekspor DSL ke format JSON/TechDocs lalu mempublikasikannya ke storage bucket Backstage.
   * C. Menulis ulang kode arsitektur di JavaScript Backstage runtime.
   * D. Mengakses database Backstage secara langsung via SQL dari mesin lokal arsitek.
   * *Jawaban yang benar:* B. CI/CD automation pipeline menjamin model arsitektur terkompilasi dan terpublikasi ke portal pengembang secara kontinu tanpa intervensi manual.

10. **Apa bahaya terbesar dari siklus dependensi (*cyclic dependency*) antar-paket dalam sistem perangkat lunak berskala besar?**
    * A. Mengurangi efisiensi kompresi file zip.
    * B. Menyebabkan dependensi transitif tak terbatas, menghancurkan isolasi pengujian modular, dan memicu *ripple effect* saat terjadi perubahan kode.
    * C. Menyebabkan file binary bertambah ukurannya dua kali lipat.
    * D. Memaksa arsitek menulis ulang seluruh ADR dari awal.
    * *Jawaban yang benar:* B. Siklus dependensi mengubah modul-modul independen menjadi sebuah unit monolitik tersembunyi yang mustahil diuji secara terisolasi.

---

#### Bagian C: Skenario Kasus Produksi (Production Scenarios)
11. **Skenario 1:**
    Sebuah tim perbankan menemukan bahwa waktu eksekusi ArchUnit di CI meningkat tajam dari **45 detik menjadi 11 menit** seiring pertumbuhan basis kode menjadi 8.000 file Java. Hal ini mengakibatkan komplain developer dan desakan untuk mematikan fitness function.
    **Solusi teknis arsitektur apa yang paling presisi untuk mengatasi masalah ini tanpa mengorbankan keamanan arsitektur?**
    * A. Menghapus ArchUnit dan kembali ke code review manual oleh Lead Architect.
    * B. Memecah eksekusi: hanya impor paket yang mengalami perubahan menggunakan deteksi `git diff` pada pre-merge PR, dan jalankan pemindaian penuh 100% kelas secara asinkron di nightly build.
    * C. Mengalokasikan RAM runner CI hingga 64GB tanpa mengubah cakupan pemindaian class.
    * D. Mengabaikan package domain dan hanya memindai package presentation.
    * *Jawaban yang benar:* B. Optimasi AST/Bytecode scanning berbasis delta diff pada level PR mempertahankan developer feedback loop yang cepat, sementara nightly build menjamin integritas global sistem secara menyeluruh.

12. **Skenario 2:**
    Perusahaan Anda memutuskan memodernisasi protokol komunikasi internal antar microservices dari REST JSON synchronous menjadi Event-Driven via Apache Kafka. Terdapat ADR-021 lama yang mewajibkan seluruh komunikasi service menggunakan REST berstandar OpenAPI 3.0.
    **Langkah operasional governance apa yang harus dijalankan tim arsitektur?**
    * A. Mengedit file ADR-021 langsung dan menghapus semua penyebutan OpenAPI, lalu menggantinya dengan Kafka.
    * B. Menghapus ADR-021 dari repositori Git agar tidak ada kebingungan.
    * C. Menerbitkan ADR-055 baru berstatus `ACCEPTED` yang mendeklarasikan event-driven via Kafka, sekaligus memutasikan status ADR-021 menjadi `SUPERSEDED` dengan mencantumkan tautan timbal-balik (*bidirectional link*) ke ADR-055 di metadata.
    * D. Membiarkan ADR-021 tetap seperti semula dan mengabaikan dokumentasi karena Kafka sudah menjadi standar defacto.
    * *Jawaban yang benar:* C. Mempertahankan riwayat keputusan masa lalu (*immutable audit trail*) dengan status mutasi yang jelas adalah prinsip mendasar dari tata kelola arsitektur profesional.

13. **Skenario 3:**
    Dalam audit arsitektur mendadak, ditemukan bahwa salah satu tim backend mengimpor pustaka `org.apache.httpclient` langsung di dalam kelas entitas domain inti (`Order.java`) untuk memanggil API diskon eksternal saat validasi saldo. ArchUnit fitness function tidak menangkap hal ini karena rule yang ada hanya melarang paket `com.enterprise.infrastructure..`.
    **Bagaimana arsitek harus mendesain ulang fitness function agar pelanggaran serupa tidak dapat lolos lagi di masa depan?**
    * A. Menambahkan nama pustaka `org.apache.httpclient` ke daftar hitam (*blacklist*) package rule secara spesifik.
    * B. Mengubah pendekatan dari *Blacklisting* ke *Whitelisting*: tetapkan bahwa kelas-kelas di paket domain hanya diizinkan bergantung pada package bahasa standar (seperti `java.lang..`, `java.math..`, `java.time..`) dan antarmuka domain internalnya sendiri.
    * C. Melarang tim menggunakan HTTP client di seluruh aplikasi.
    * D. Menulis unit test fungsional untuk menguji timeout koneksi diskon.
    * *Jawaban yang benar:* B. Pendekatan Whitelisting pada Core Domain menjamin bahwa domain logic sepenuhnya terisolasi (*clean*) dari segala jenis dependensi eksternal, baik pustaka pihak ketiga yang sudah ada maupun yang akan ditambahkan di masa depan.

---

### 16. Summary

1. **Evolutionary Governance:** Dokumentasi arsitektur tidak lagi berupa artefak pasif yang terpisah dari proses rekayasa sistem, melainkan sistem hidup (*living ecosystem*) yang diatur oleh kode deklaratif dan dievaluasi secara otomatis (*active fitness functions*).
2. **Architecture as Code (AaC):** Dengan memodelkan batasan desain ke dalam bahasa pemrograman (seperti ArchUnit atau Structurizr DSL), arsitek dapat menggeser verifikasi integritas sistem ke tahap sedini mungkin (*shift-left architecture verification*) pada siklus pengembangan perangkat lunak.
3. **Traceability & State Integrity:** Siklus hidup ADR merefleksikan graf evolusi keputusan organisasi. Mutasi status dari `PROPOSED` hingga `SUPERSEDED` harus diatur dengan aturan integritas relasional yang ketat untuk mencegah kebingungan teknis dan *architectural rot*.
4. **Pragmatic Automation:** Implementasi tata kelola arsitektur harus memperhatikan latensi CI/CD, kurva belajar tim, serta keandalan rule agar tidak menciptakan friksi kontraproduktif terhadap produktivitas tim pengembang (*developer velocity*).